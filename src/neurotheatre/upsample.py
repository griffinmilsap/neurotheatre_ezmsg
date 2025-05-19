import typing
import numpy as np

from scipy.signal import resample
import ezmsg.core as ez
from ezmsg.util.messages.axisarray import AxisArray, slice_along_axis, replace
from ezmsg.util.generator import consumer
from ezmsg.sigproc.base import GenAxisArray

@consumer
def upsample(
    axis: str | None = None, factor: int | None = None
) -> typing.Generator[AxisArray, AxisArray, None]:
    """
    Construct a generator that yields an upsampled version of the data .send() to it.
    Upsampled data is interpolated using Fourier-based resampling.

    Args:
        axis: The name of the axis along which to upsample.
            Note: The axis must exist in the message .axes and be of type AxisArray.LinearAxis.
        factor: Upsampling factor.

    Returns:
        A primed generator object ready to receive an :obj:`AxisArray` via `.send(axis_array)`
        and yields an :obj:`AxisArray` with its data upsampled.
    """
    if factor < 1:
        raise ValueError("Upsample factor must be at least 1 (no upsampling)")

    msg_out = AxisArray(np.array([]), dims=[""])

    while True:
        msg_in: AxisArray = yield msg_out

        if axis is None:
            axis = msg_in.dims[0]
        axis_info = msg_in.get_axis(axis)
        axis_idx = msg_in.get_axis_idx(axis)

        n_samples = msg_in.data.shape[axis_idx]
        upsampled_n_samples = n_samples * factor

        # Perform Fourier-based resampling
        upsampled_data = resample(msg_in.data, upsampled_n_samples, axis=axis_idx)

        # Update axis information
        upsampled_axes = {
            **msg_in.axes,
            axis: replace(
                axis_info,
                gain=axis_info.gain / factor,
            ),
        }

        msg_out = replace(msg_in, data=upsampled_data, axes=upsampled_axes)


class UpsampleSettings(ez.Settings):
    """
    Settings for :obj:`Upsample` node.
    """
    axis: str | None = None
    factor: int | None = None

class Upsample(GenAxisArray):
    """:obj:`Unit` for :obj:`upsample`."""

    SETTINGS = UpsampleSettings

    def construct_generator(self):
        self.STATE.gen = upsample(
            axis=self.SETTINGS.axis,
            factor=self.SETTINGS.factor
        )