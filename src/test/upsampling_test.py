import numpy as np
from scipy.signal import resample
import matplotlib.pyplot as plt

# Original signal
x = np.linspace(0, 10, 20)
y = np.sin(x)

# Upsample to 60 points
num_upsampled = 60
y_upsampled = resample(y, num_upsampled)
x_upsampled = np.linspace(0, 10, num_upsampled)

# Plotting
plt.figure(figsize=(10, 6))
plt.plot(x, y, 'o-', label='Original signal')
plt.plot(x_upsampled, y_upsampled, 'x-', label='Upsampled signal')
plt.legend()
plt.title('Upsampling with scipy.signal.resample')
plt.xlabel('X')
plt.ylabel('Y')
plt.grid(True)
plt.show()