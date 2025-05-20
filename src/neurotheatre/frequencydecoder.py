import typing
from dataclasses import dataclass, field, replace

import numpy as np
from numpy.linalg import svd

import ezmsg.core as ez
from ezmsg.util.generator import consumer
from ezmsg.util.messages.axisarray import AxisArray
from ezmsg.sigproc.sampler import SampleMessage, SampleTriggerMessage


@dataclass
class FrequencyDecodeMessage(AxisArray):
    freqs: typing.List[float] = field(default_factory = list) # Use a coordinate/linear axis for this
    trigger: typing.Optional[SampleTriggerMessage] = None # Use attrs for this


@consumer
def frequency_decode(
    time_axis: typing.Union[str, int] = 0,
    harmonics: int = 0,
    freqs: typing.List[float] = [],
    max_int_time: float = 0,
    softmax_beta: float = 1.0,
    freq_axis: str = 'freq',
    window_axis: typing.Optional[str] = None,
    calc_corrs: bool = True,
) -> typing.Generator[FrequencyDecodeMessage, typing.Union[SampleMessage, AxisArray], None]:
    """
    # `frequency_decode`
    Evaluates the presence of periodic content at various frequencies in the input signal using CCA  
    
    ## Further reading:  
    * [Nakanishi et. al. 2015](https://doi.org/10.1371%2Fjournal.pone.0140703)
    
    ## Parameters:
    * `time_axis (str|int)`: The time axis in the data array to look for periodic content within.
        Default: 0  - choose the first axis in the first input.

    * `harmonics (int)`: The number of additional harmonics beyond the fundamental to use for the 'design' matrix
        Many periodic signals are not pure sinusoids, and inclusion of higher harmonics can help evaluate the 
        presence of signals with higher frequency harmonic content
        Default: 0 - generate a design matrix using only the fundamental frequency.

    * `freqs (List[float])`: Frequencies (in hz) to evaluate the presence of within the input signal
        Default: [] an empty list; frequencies will be found within the input SampleMessages
        AxisArrays have no good place to put this metadata, so specify frequencies here if only AxisArrays
        will be passed as input to the generator.  If a SampleMessage is passed in, this generator looks
        at the `trigger` field of the SampleMessage (a SampleTriggerMessage) and looks for the `freqs` attribute
        within that trigger for a list of frequencies to evaluate.  This field is present in the 
        SSVEPSampleTriggerMessage defined in ezmsg.tasks.ssvep from the ezmsg-tasks package.

    * `max_int_t (float)`: Maximum integration time (in seconds) to use for calculation.  
        0 (default): Use all time provided for the calculation.
        Useful for artificially limiting the amount of data used for the CCA method to evaluate
        the necessary integration time for good decoding performance
    
    * `softmax_beta (float)`: Beta parameter for softmax on output --> "probabilities"  
        1.0 (default): Use the shifted softmax transformation to output 0-1 probabilities
        If 0.0, the maximum singular value of the SVD for each design matrix is output

    * `freq_axis (str)`: Name for axis to put frequency outputs on
        'freq' (default)
    
    * `window_axis (str | None)`: Name of an axis to treat as a window axis
        None (default): Input should just be treated as one observation
        If specified, each element on the "window" axis will be treated as a separate observation
        and the window axis information will be preserved

    * `calc_corrs (bool)`: Calculate and use canonical correlation values instead of SVD intermediates
        True (default): Calculate the correlation of the most significant canonical projection
        If False, just output singular values instead which are unbounded, but less computationally 
        expensive to calculate.  Interestingly, seems like somewhat of a worse metric?
 
    ## Sends:
    * `AxisArray` or `SampleMessage` containing buffers of data to evaluate
    Yields:
    * `FrequencyDecodeMessage | None`: "Posteriors" of frequency decoding
        This is calculated as the softmax of the highest canonical correlations between each design matrix and the data
    """
    
    harmonics = max(0, harmonics)
    max_int_time = max(0, max_int_time)
    output: FrequencyDecodeMessage = FrequencyDecodeMessage(np.array([]), dims = [""])

    while True:
        input = yield output

        if input.data.size == 0:
            output = input
            continue

        test_freqs = freqs
        trigger = None
        if isinstance(input, SampleMessage):
            trigger = input.trigger
            input = input.sample
            if len(test_freqs) == 0:
                test_freqs = getattr(trigger, 'freqs', []) 

        window_axis_obj = input.axes.get(window_axis, None) if window_axis else None
        input_aas = [aa for aa in input.iter_over_axis(window_axis)] if window_axis is not None else [input]

        outputs = []
        for input_aa in input_aas:

            t_ax = input_aa.ax(time_axis)
            fs = 1.0 / t_ax.axis.gain
            t = t_ax.values - t_ax.axis.offset
            max_samp = int(max_int_time * fs) if max_int_time else len(t)
            t = t[:max_samp]

            if len(test_freqs) == 0:
                ez.logger.warning('no frequencies to test')
                output = None
                continue

            cv = []
            for test_freq in test_freqs:

                # Create the design matrix of base frequency and requested harmonics
                design = []
                for harm_idx in range(harmonics + 1):
                    f = test_freq * (harm_idx + 1)
                    w = 2.0 * np.pi * f * t
                    design.append(np.sin(w))
                    design.append(np.cos(w))
                design = np.array(design) # time is now dim 1

                # We only care about highest canonical correlation
                # which can be calculated using singular value decomposition
                # https://numerical.recipes/whp/notes/CanonCorrBySVD.pdf
                # time-axis moved to dim 0, all other axes flattened to dim 1
                X = input_aa.as2d(time_axis)[:max_samp, ...] 
                X = X - X.mean(0) # Method works best with zero-mean on time dimension.
                X = X / X.std(0)
                
                if calc_corrs:
                    # Calculate the canonical correlation of the first (strongest) canonical projection
                    result = svd(design @ X, compute_uv = True, full_matrices = False)
                    design_proj = result.U.T[:1, ...] @ design
                    data_proj = result.Vh[:1, ...] @ X.T
                    cv.append(np.corrcoef(design_proj, data_proj)[0,1])

                else:
                    # singular values are porportional to canonical correlations; 
                    # SVD guarantees max singular value is element 0
                    # Result isn't quite as useful as correlation, but this is much faster to calculate
                    cv.append(svd(design @ X, compute_uv = False)[0])

            cv = np.array(cv)
            cv = calc_softmax(cv, axis = 0, beta = softmax_beta) if softmax_beta != 0 else cv

            if trigger and hasattr(trigger, 'decode'):
                trigger = replace(trigger, decode = np.argmax(cv).item())

            outputs.append(
                FrequencyDecodeMessage(
                    cv,
                    dims = [freq_axis],
                    freqs = test_freqs,
                    trigger = trigger
                )
            )
        
        if window_axis is None:
            output = outputs[0]
        else:
            output = AxisArray.concatenate(*outputs, dim = window_axis, axis = window_axis_obj)


class FrequencyDecodeSettings(ez.Settings):
    harmonics: int = 0
    time_axis: typing.Union[str, int] = 0
    freqs: typing.List[float] = field(default_factory = list)
    max_int_time: float = 0
    softmax_beta: float = 1.0
    freq_axis: str = 'freq'
    window_axis: typing.Optional[str] = None
    calc_corrs: bool = True


class FrequencyDecodeState(ez.State):
    gen: typing.Generator[typing.Optional[FrequencyDecodeMessage], typing.Union[SampleMessage, AxisArray], None]


class FrequencyDecode(ez.Unit):
    SETTINGS = FrequencyDecodeSettings
    STATE = FrequencyDecodeState

    INPUT_SETTINGS = ez.InputStream(FrequencyDecodeSettings)
    INPUT_SIGNAL = ez.InputStream(typing.Union[AxisArray, SampleMessage])
    OUTPUT_DECODE = ez.OutputStream(typing.Optional[FrequencyDecodeMessage])
    OUTPUT_TRIGGER = ez.OutputStream(typing.Optional[SampleTriggerMessage])

    async def create_generator(self, settings: FrequencyDecodeSettings) -> None:
        self.STATE.gen = frequency_decode(
            harmonics = settings.harmonics,
            time_axis = settings.time_axis,
            freqs = settings.freqs,
            max_int_time = settings.max_int_time,
            softmax_beta = settings.softmax_beta,
            freq_axis = settings.freq_axis,
            window_axis = settings.window_axis,
            calc_corrs = settings.calc_corrs
        )

    async def initialize(self) -> None:
        await self.create_generator(self.SETTINGS)

    @ez.subscriber(INPUT_SETTINGS)
    async def on_settings(self, msg: FrequencyDecodeSettings) -> None:
        await self.create_generator(msg)

    @ez.subscriber(INPUT_SIGNAL)
    @ez.publisher(OUTPUT_DECODE)
    @ez.publisher(OUTPUT_TRIGGER)
    async def on_signal(self, msg: typing.Union[AxisArray, SampleMessage]) -> typing.AsyncGenerator:
        output = self.STATE.gen.send(msg)
        yield self.OUTPUT_DECODE, output
        trigger = getattr(output, 'trigger', None)
        if trigger is not None:
            yield self.OUTPUT_TRIGGER, trigger

    
def calc_softmax(cv: np.ndarray, axis: int, beta: float = 1.0):
    # Calculate softmax with shifting to avoid overflow
    # (https://doi.org/10.1093/imanum/draa038)
    cv = cv - cv.max(axis = axis)
    cv = np.exp(beta * cv)
    cv = cv / np.sum(cv, axis = axis)
    return cv