import pyvisa
import numpy as np
import time
import matplotlib.pyplot as plt


RESOURCE = "TCPIP0::10.0.142.151::inst0::INSTR"


rm = pyvisa.ResourceManager()

scope = rm.open_resource(RESOURCE)

# -------------------
# CRITICAL SETTINGS
# -------------------

scope.timeout = 20000
scope.chunk_size = 1024000
scope.read_termination = None
scope.write_termination = "\n"

scope.clear()
scope.write("*CLS")

print(scope.query("*IDN?"))


# -------------------
# STOP + ARM
# -------------------

scope.write("ACQ:STOPAFTER SEQ")
scope.write("ACQ:STATE 1")
scope.query("*OPC?")


# -------------------
# WAVEFORM SETUP
# -------------------

scope.write("DATA:SOU CH1")
scope.write("DATA:START 0")
scope.write("DATA:STOP 5000")
scope.write("DATA:ENC RIB")
scope.write("DATA:WIDTH 2")
scope.write("WFMOUTPRE:BYT_NR 2")

scope.query("*OPC?")


# -------------------
# SCALING
# -------------------

ymult = float(scope.query("WFMPRE:YMULT?"))
yoff  = float(scope.query("WFMPRE:YOFF?"))
yzero = float(scope.query("WFMPRE:YZERO?"))
xincr = float(scope.query("WFMPRE:XINCR?"))


# -------------------
# READ WAVEFORM
# -------------------

scope.write("CURVE?")
raw_data = scope.read_raw()
time.sleep(0.1)

if raw_data[0:1] != b'#':
    raise ValueError("Expected binary block with '#' header")

header_len_digits = int(raw_data[1:2])
num_bytes = int(raw_data[2:2 + header_len_digits])
bin_start = 2 + header_len_digits
bin_end = bin_start + num_bytes
bin_data = raw_data[bin_start:bin_end]

if len(bin_data) % 2 != 0:
    raise ValueError("Binary data lenght is not a multiple of 2 bytes")

# -------------------
# CONVERT
# -------------------
waveform = np.frombuffer(bin_data, dtype='>i2')
volts = (waveform - yoff) * ymult + yzero
time_axis = np.arange(len(volts)) * xincr


print("Points:", len(volts))


# -------------------
# PLOT
# -------------------

plt.plot(time_axis * 1e9, volts)
plt.xlabel("Time (ns)")
plt.ylabel("Voltage (V)")
plt.grid()
plt.show()


scope.close()
rm.close()

