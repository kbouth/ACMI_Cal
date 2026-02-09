from pylogix import PLC
from math import sqrt
import numpy as np
import matplotlib.pyplot as plt
import serial
from time import sleep
import pyvisa as visa
import socket

props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)

plt.ion()

# Setup for Prologix USB-Ethernet converter for the HP8114A
PORT = "COM4"      # Windows example (e.g., COM3)

ser = serial.Serial(
    port=PORT,
    baudrate=115200,   # Value doesn't really matter for Prologix USB
    timeout=1
)
sleep(0.5)  # Give the port time to settle

def HPwrite(cmd):
    ser.write((cmd + "\n").encode("ascii"))

def HPread():
    return ser.readline().decode("ascii").strip()

# Put Prologix in controller mode and set GPIB address
HPwrite("++mode 1")      # Controller mode
HPwrite("++addr 14")      # Change to HP8114A's GPIB address
HPwrite("++auto 1")      # Automatically read response after write
HPwrite("*IDN?")
response = HPread()
print(response)
model = int(response[18:22])
if(model != 8114):
    print('HP8114A Pulse Generator NOT FOUND...exiting!')
    exit()
else:
    print('HP8114A Pusle Generator FOUND.')   
    HPwrite(':SOUR:VOLT 0.0')
    sleep(0.5)
    HPwrite(':OUTP:POL NEG')
    sleep(0.5)
    HPwrite(':SOUR:PULS:DEL 5US')
    sleep(0.5)
    HPwrite(':SOUR:PULS:WIDT 50.0NS')
    sleep(0.5)
    HPwrite(':SOUR:VOLT 1.0')
    sleep(0.5)
    
rm = visa.ResourceManager()
scope = rm.open_resource('TCPIP0::10.0.128.110::inst0::INSTR')
response = scope.query('*IDN?')
serial_number = int(response[18:24])
if(serial_number != 13046):
    print('Tektronix MSO64B Scope NOT FOUND...exiting!')
    exit()
else:
    print('Tektronix MSO64B Scope FOUND.')
    
with PLC() as comm:
    comm.IPAddress = '10.0.128.47'
    
    device = comm.GetModuleProperties(0).Value
    if(device.ProductName != "1768-L43S/B LOGIX5343SAFETY"):
        print("1768-L43S/B PLC NOT FOUND...exiting")
        exit()
    else:
        print("1768-L43S/B PLC FOUND.\n\n")
        
# Declare the PLC Tags for this test:
Bmtag = 'ACMI_BEAM_Q'
STABtag = 'ACMI_ST1_QAB'
STBAtag = 'ACMI_ST1_QBA'

#Get the Current ACMI Calibration Parameters:
bm1 = float(comm.Read(Bmtag).Value)

print(bm1)

#############################################################################################
# Part One: HP8114A Pulser connected directly to the scope.  Measurement of the charge for
# each of 24 different pulse amplitudes from 1V to 24V in 1V steps.  The pulse width is fixed
# at 50.3nSec for all pulse amplitudes.
#############################################################################################
input("Connect cable from HP8114A Pulser to Oscilloscope Channel 1.  Hit <CR> when done.")
fname = input("Enter file name for data (No Extension): ")

fq,axq = plt.subplots(1,2,figsize=(12,6))

CH1scale=[0.2,0.5,0.5,0.5,1,1,1,1,1,2,2,2,2,2,2,2,2,2,5,5,5,5,5] #in Volts/Division on Scope
Vp = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23] #in Volts for Pulse Amplitude

#Set up the scope:
scope.write('HOR:RECO 5000')
scope.write('TRIGGER:A:MODE NORM')
scope.write('TRIGGER:A:TYPE EDGE')
scope.write('TRIGGER:A:EDGE:SOURCE CH1')
scope.write('TRIGGER:A:EDGE:SLOPE FALL')
scope.write('TRIGGER:A:EDGE:COUPLING DC')
scope.write('HORIZONTAL:MODE MANUAL')
scope.write('HORIZONTAL:MODE:SAMPLERATE 25.0E9')
scope.write('HORIZONTAL:SCALE 4e-8')
scope.write('HORIZONTAL:POS 10')
scope.write('*WAI')
scope.write('CH1:SCALE 0.200')
scope.write('CH1:POS 4.5')

Qtest = []
Itest = []
Vtest= []   
f = open(fname+".txt","w")

for j in range(0,23):
    HPwrite(':SOUR:VOLT '+str(Vp[j]))
    sleep(1)
    sleep(1)
    Vtest.append(Vp[j])
    Qhist=[]
    Ihist=[]
    for N in range(0,25):
        scope.write('CH1:SCALE '+str(CH1scale[j]))
        scope.write('TRIGGER:A:LEVEL:CH1 '+str(-CH1scale[j]/2.0))
        scope.write('ACQUIRE:STOPAFTER SEQUENCE')
        scope.write('ACQUIRE:STATE 1')
        scope.write('*WAI')
    
        good=0
        while(good==0):
            try:
                scope.write('ACQUIRE:STOPAFTER SEQUENCE')
                scope.write('ACQUIRE:STATE 1')
                scope.write('*WAI')
                scope.write('DATA:SOU CH1')
                scope.write('DATA:START 0')
                scope.write('DATA:STOP 5000')
                scope.write('DATA:WIDTH 2')
                scope.write('DATA:ENC RIB')
                scope.write('WFMOUTPRE:BYT_NR 2')

                scope.query('*OPC?')
    
                ymult1 = float(scope.query('WFMPRE:YMULT?'))
                yzero1 = float(scope.query('WFMPRE:YZERO?'))
                yoff1 = float(scope.query('WFMPRE:YOFF?'))
                xincr1 = float(scope.query('WFMPRE:XINCR?'))

                scope.write('CURVE?')

                data1 = scope.read_raw()
                sleep(0.1)
                good = 1
            except:
                good = 0
        header_len_digits = int(data1[1:2])
        num_bytes = int(data1[2:2+ header_len_digits])
        bin_start = 2 + header_len_digits
        bin_end = bin_start + num_bytes
        ADC_wave1 = data1[bin_start:bin_end]
        print(len(ADC_wave1))
        CH1 = []

        waveform = np.frombuffer(ADC_wave1, dtype='>i2')   
        Vq = (waveform - yoff1) * ymult1 + yzero1
        Tq = np.arange(len(Vq)) * xincr1
        
        BL = sum(Vq[0:50])/50.0
        Vq = np.subtract(Vq,BL)
        for i in range(0,len(Vq)):
            if(Vq[i]>0): Vq[i] = 0
        axq[0].clear()
        axq[0].plot(Tq,Vq,label='Scope Data')
        axq[0].grid(color='lightgray',linestyle='-',linewidth=1)
        axq[0].set_xlabel("Time (nSec)")
        axq[0].set_ylabel("Voltage")
        axq[0].legend(loc='lower right')
        Integral = abs(sum(Vq)*xincr1*1000000000)
        Ihist.append(Integral)
        Q = abs(sum(Vq)*xincr1*2e7)
        Qhist.append(Q)
        Qavg = sum(Qhist)/len(Qhist)
        Iavg = sum(Ihist)/len(Ihist)
        line = str(j)+","+str(N)+","+str(Vp[j])+","+str(round(Integral,3))+","+str(round(Q,4))+"\n"
        f.write(line)
        axq[0].text(0.6, 0.93, 'N:'+str(N),
                transform=axq[0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        axq[0].text(0.6, 0.85, 'Qavg:'+str(round(Qavg,4))+"nC",
                transform=axq[0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        axq[0].text(0.6, 0.77, 'Qlast:'+str(round(Q,4))+"nC",
                transform=axq[0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        axq[0].text(0.6, 0.65, 'Iavg:'+str(round(Iavg,3))+"nVS",
                transform=axq[0].transAxes, fontsize=12,verticalalignment='top', bbox=props)   
        axq[0].text(0.6, 0.57, 'Ilast:'+str(round(Integral,3))+"nVS",
                transform=axq[0].transAxes, fontsize=12,verticalalignment='top', bbox=props)      
        plt.pause(0.1)
    Qtest.append(Qavg)
    Itest.append(Iavg)
    axq[1].clear()
    axq[1].plot(Vtest,Qtest,'-o',markersize=4)
    axq[1].grid(color='lightgray',linestyle='-',linewidth=1)
    axq[1].set_xlabel("Pulser Amplitude (Volts)")
    axq[1].set_ylabel("Measured Test Charge (nC)") 
    plt.pause(0.1)

HPwrite(':SOUR:VOLT 1.0\n')
sleep(5)  
fq.savefig(fname+'testpulse.png')

# Part Two: HP8114A Pulser connected directly to the ICT Test Input with the 6dB attenuator.
# The ICT Charge Output is now connected to the ACMI.  Measurement of the charge for
# each of 24 different pulse amplitudes from 1V to 24V in 1V steps.  The pulse width is fixed
# at 50.3nSec for all pulse amplitudes.

"Remove cable from Oscilloscope and add a 6Db attenuator to the end of the cable"
input("Remove cable from Oscilloscope and add a 6Db attenuator to the end of the cable.  Hit <CR> when done.")
input("Connect attenuator to the ICT test input.  Hit <CR> when done.")
input("Connect ICT Charge Output to ACMI input.  Hit <CR> when done.")
    
Vp = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23] #in Volts for Pulse Amplitude

fst,axst = plt.subplots(2,2,figsize=(11,9))
fbm,axbm = plt.subplots(2,2,figsize=(11,9))

Vtest = []
BM = []
STA = []
STB = []
for j in range(0,23):
    HPwrite(':SOUR:VOLT '+str(Vp[j]))
    sleep(1)
    sleep(3)
    Vtest.append(Vp[j])
    B=[]
    TA=[]
    TB=[]
    Qerr=[]
    print(comm.Read(Bmtag).Value)
    for n in range(0,16):
        B.append(float(comm.Read(Bmtag).Value))
        TA.append(float(comm.Read(STABtag).Value))
        TB.append(float(comm.Read(STBAtag).Value))
        print(n,round(Qtest[j],3),B[n],TA[n],TB[n])
        sleep(2.2)
        
    BM.append(np.mean(B))
    STA.append(np.mean(TA))
    STB.append(np.mean(TB))
    print("Averages:",j,Vp[j],Qtest[j],BM[j],STA[j],STB[j])
    mess = str(j)+','+str(Vp[j])+','+str(round(Qtest[j],4))+','+str(round(BM[j],4))+','+str(round(STA[j],4))+','+str(round(STB[j],4))+'\n'
    f.write(mess)
    axbm[0][0].clear()
    axbm[0][1].clear()
    axbm[1][0].clear()
    axbm[1][1].clear()    
    axbm[0][0].plot(Qtest[0:len(BM)],BM,'-o',markersize=6)
    axbm[0][0].grid(True)
    axbm[0][0].set_xlabel("Test Pulse Charge (nC)")
    axbm[0][0].set_ylabel("Beam Charge (nC)")

    if(len(BM)>3):
        #Do not include the saturated ADC data in the calibration calculations
        L = len(BM)
        if(L>19): L=19
         
        axbm[1][0].plot(Qtest[0:L],BM[0:L],'-o',markersize=6)
        axbm[1][0].grid(True)
        axbm[1][0].set_xlabel("Test Pulse Charge (nC)")
        axbm[1][0].set_ylabel("Beam Charge (nC)")
        pfit = np.polyfit(Qtest[0:L],BM[0:L],1)
        FitCoef = np.corrcoef(Qtest[0:L],BM[0:L])
        mess = 'Linear: '+str(round(pfit[0],4))+'nC/nC\nOffset:'+str(round(pfit[1],3))+'nC\nCorrelation:'+str(round(FitCoef[0][1],4))
        axbm[1][0].text(0.05, 0.93, mess,
            transform=axbm[1][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        
        axbm[0][1].plot(BM[0:L],Qtest[0:L],'o',markersize=6,label="Data")
        axbm[0][1].grid(True)
        axbm[0][1].set_xlabel("Test Pulse Charge (nC)")
        axbm[0][1].set_ylabel("Beam Charge (nC)")

        Qerr = np.multiply(np.divide(np.subtract(BM[0:L],Qtest[0:L]),Qtest[0:L]),100.0)
        Qerr = np.abs(Qerr)
        axbm[1][1].plot(Qtest[0:L],Qerr,'-o',markersize=6)
        axbm[1][1].grid(True)
        axbm[1][1].set_ylabel("Q Error) (%)")
        axbm[1][1].set_xlabel("Test Pulse Charge (nC)")
        
    axst[0][0].clear()
    axst[0][1].clear()
    axst[1][0].clear()
    axst[1][1].clear()    
    axst[0][0].plot(Qtest[0:len(STA)],STA,'-o',markersize=6)
    axst[0][0].grid(True)
    axst[0][0].set_xlabel("Test Pulse Charge (nC)")
    axst[0][0].set_ylabel("Self Test (A-B) Charge(nC)")
    
    axst[0][1].plot(Qtest[0:len(STB)],STB,'-o',markersize=6)
    axst[0][1].grid(True)
    axst[0][1].set_xlabel("Test Pulse Charge (nC)")
    axst[0][1].set_ylabel("Self Test (B-A) Charge (nC)")
    
    if(len(STA)>3):
        #Do not include the saturated ADC data in the calibration calculations
        L = len(STA)
        if(L>19): L=19
         
        axst[1][0].plot(Qtest[0:L],STA[0:L],'-o',markersize=6)
        axst[1][0].grid(True)
        axst[1][0].set_xlabel("Test Pulse Charge (nC)")
        axst[1][0].set_ylabel("Self Test (A-B) Charge (nC)")
        pfit = np.polyfit(Qtest[0:L],STA[0:L],1)
        FitCoef = np.corrcoef(Qtest[0:L],STA[0:L])
        mess = 'Linear: '+str(round(pfit[0],4))+'nC/nC\nOffset:'+str(round(pfit[1],3))+'nC\nCorrelation:'+str(round(FitCoef[0][1],4))
        axst[1][0].text(0.05, 0.93, mess,
            transform=axst[1][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        pfit = np.polyfit(Qtest[0:L],STB[0:L],1)
        FitCoef = np.corrcoef(Qtest[0:L],STB[0:L])
        mess = 'Linear: '+str(round(pfit[0],4))+'nC/nC\nOffset:'+str(round(pfit[1],3))+'nC\nCorrelation:'+str(round(FitCoef[0][1],4))        
        axst[1][1].plot(Qtest[0:L],STB[0:L],'-o',markersize=6)
        axst[1][1].grid(True)
        axst[1][1].set_xlabel("Test Pulse Charge (nC)")
        axst[1][1].set_ylabel("Self Test (B-A) Charge (nC)")

        axst[1][1].text(0.05, 0.93, mess,
            transform=axst[1][1].transAxes, fontsize=12,verticalalignment='top', bbox=props) 

    plt.pause(0.1)

HPwrite(':SOUR:VOLT 0.0\n')
sleep(1)
fbm.savefig(fname+'beam.png')
fst.savefig(fname+'selftest.png')
plt.show(block=True)
