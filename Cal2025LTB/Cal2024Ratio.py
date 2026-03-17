import visa
import numpy as np
from struct import unpack
import matplotlib.pyplot as plt
from matplotlib.widgets import TextBox
from time import sleep
import epics
from matplotlib.widgets import Button
import telnetlib as tn

props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)

plt.ion()
fq,axq = plt.subplots(2,2,figsize=(12,10))
fr,axr = plt.subplots(1,2,figsize=(12,6))
###############################################################################
# Part One: HP8114A Pulser connected directly to the scope.  Measurement of the 
# charge for each of 24 different pulse amplitudes from 1V to 24V in 1V steps.
# The pulse width is fixed at 50.3nSec for all pulse amplitudes.
###############################################################################
input("Connect cable from HP8114A Pulser to Oscilloscope Channel 1.  Hit <CR> when done.")
fname = input("Enter file name for data (No Extension): ")

CH1scale=[0.2,0.5,0.5,0.5,1,1,1,1,1,2,2,2,2,2,2,2,2,2,5,5,5] #in Volts/Division on Scope
Vp = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21] #in Volts for Pulse Amplitude

tnet = tn.Telnet('10.0.128.131','1234')
tnet.write(b'++addr 14\n')
sleep(1)
tnet.write(b'*IDN?\n')
response = tnet.read_until(b'\n',7)
model = int(response[18:22])
if(model != 8114):
    print('HP8114A Pulse Generator NOT FOUND...exiting!')
    exit()
else:
    print('HP8114A Pusle Generator FOUND.') 
    cmd = bytes(':SOUR:VOLT 0.0\n','utf-8')
    tnet.write(cmd)
    sleep(1)
    cmd = bytes(':OUTP:POL NEG\n','utf-8')
    tnet.write(cmd)
    sleep(1)
    cmd = bytes(':SOUR:PULS:DEL 0NS\n','utf-8')
    tnet.write(cmd)
    sleep(1)
    cmd = bytes(':SOUR:PULS:WIDT 50.3pNS\n','utf-8')
    tnet.write(cmd)
    sleep(1)
    tnet.write(b':SOUR:VOLT 1.0\n')
    sleep(0.5)
    
rm = visa.ResourceManager()
scope = rm.get_instrument('USB0::0x0699::0x0530::B027138::INSTR')
response = scope.query('*IDN?')
serial_number = int(response[18:24])
if(serial_number != 27138):
    print('Tektronix MSO64B Scope NOT FOUND...exiting!')
    exit()
else:
    print('Tektronix MSO64B Scope FOUND.')



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
scope.write('CH1:SCALE 0.2')
scope.write('CH1:POS 4.5')

Qtest = []
Itest = []
Vtest= []
f = open(fname+".raw","w")
f.write("Raw Data for Test Pulse Charge Measurement:\n")

for j in range(0,21):
    cmd = bytes(':SOUR:VOLT '+str(Vp[j])+'\n','utf-8')
    tnet.write(cmd)
    sleep(1)
    Vtest.append(Vp[j])
    Qhist=[]
    Ihist=[]
    scope.write('CH1:SCALE '+str(CH1scale[j]))
    scope.write('TRIGGER:A:LEVEL:CH1 '+str(-CH1scale[j]))
    for N in range(0,25):
        scope.write('ACQUIRE:STOPAFTER SEQUENCE')
        scope.write('ACQUIRE:STATE 1')
        scope.write('*WAI')

        axq[0][0].clear()
    
        good=0
        while(good==0):
            try:
                scope.write('DATA:SOU CH1')
                scope.write('DATA:START 0')
                scope.write('DATA:STOP 5000')
                scope.write('DATA:WIDTH 2')
                scope.write('DATA:ENC RPB')
                scope.write('WFMOUTPRE:BYT_NR 2')
                ymult1 = float(scope.query('WFMPRE:YMULT?'))
                yzero1 = float(scope.query('WFMPRE:YZERO?'))
                yoff1 = float(scope.query('WFMPRE:YOFF?'))
                xincr1 = float(scope.query('WFMPRE:XINCR?'))
                scope.write('CURVE?')
                data1 = scope.read_raw()
                
                good = 1
            except:
                good = 0
        headerlen = 2 + int(data1[1])
        header = data1[:headerlen]
        ADC_wave1 = data1[headerlen:-1]
        CH1 = []
        Tq = []
        for i in range(0,len(ADC_wave1),2):
            CH1.append(256*ADC_wave1[i]+ADC_wave1[i+1])
            Tq.append(i/2)    
        Vq = np.multiply(np.subtract(CH1,CH1[0]),ymult1)

        BL = sum(Vq[0:50])/50.0
        Vq = np.subtract(Vq,BL)
        for i in range(0,len(Vq)):
            if(Vq[i]>0): Vq[i] = 0
        axq[0][0].plot(Tq,Vq)
        axq[0][0].grid(color='lightgray',linestyle='-',linewidth=1)
        axq[0][0].set_xlabel("Time (nSec)")
        axq[0][0].set_ylabel("Voltage") 
        Integral = abs(sum(Vq)*xincr1*1000000000)
        Ihist.append(Integral)
        Q = abs(sum(Vq)*xincr1*2e7)
        Qhist.append(Q)
        Qavg = sum(Qhist)/len(Qhist)
        Iavg = sum(Ihist)/len(Ihist)
        line = str(j)+","+str(N)+","+str(Vp[j])+","+str(round(Integral,3))+","+str(round(Q,4))+"\n"
        f.write(line)
        axq[0][0].text(0.6, 0.93, 'N:'+str(N),
                transform=axq[0][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        axq[0][0].text(0.6, 0.85, 'Qavg:'+str(round(Qavg,4))+"nC",
                transform=axq[0][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        axq[0][0].text(0.6, 0.77, 'Qlast:'+str(round(Q,4))+"nC",
                transform=axq[0][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        axq[0][0].text(0.6, 0.65, 'Iavg:'+str(round(Iavg,3))+"nVS",
                transform=axq[0][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)   
        axq[0][0].text(0.6, 0.57, 'Ilast:'+str(round(Integral,3))+"nVS",
                transform=axq[0][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)      
        plt.pause(0.1)
    Qtest.append(Qavg)
    Itest.append(Iavg)
    axq[0][1].clear()
    axq[0][1].plot(Vtest,Qtest,'-o',markersize=4)
    axq[0][1].grid(color='lightgray',linestyle='-',linewidth=1)
    axq[0][1].set_xlabel("Pulser Amplitude (Volts)")
    axq[0][1].set_ylabel("Measured Test Charge (nC)") 
    plt.pause(0.1)
#################################################################################    
# Part Two: HP8114A Pulser connected directly to the ICT Test Input with the 6dB attenuator.
# The ICT Charge Output is now connected to the scope.  Measurement of the charge for
# each of 24 different pulse amplitudes from 1V to 24V in 1V steps.  The pulse width is fixed
# at 50.3nSec for all pulse amplitudes.
#################################################################################
input("Remove cable from Oscilloscope and add a 6Db attenuator to the end of the cable.  Hit <CR> when done.")
input("Connect attenuator to the ICT test input.  Hit <CR> when done.")
input("Connect ICT Charge Output to Oscilloscope channel 1.  Hit <CR> when done.")
    
CH1scale=[0.005,0.01,0.01,0.02,0.02,0.02,0.02,0.02,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,0.05,
          0.1,0.1] #in Volts/Division on Scope
Vp = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21] #in Volts for Pulse Amplitude

Qict = []
Iict = []
Vict = []
f.write("Raw Data for ICT Charge Measurement:\n")
for j in range(0,21):
    cmd = bytes(':SOUR:VOLT '+str(Vp[j])+'\n','utf-8')
    tnet.write(cmd)
    sleep(1)
    Vict.append(Vp[j])
    Qhist=[]
    Ihist=[]
    scope.write('CH1:SCALE '+str(CH1scale[j]))
    scope.write('TRIGGER:A:LEVEL:CH1 '+str(-CH1scale[j]))
    for N in range(0,25):
        scope.write('ACQUIRE:STOPAFTER SEQUENCE')
        scope.write('ACQUIRE:STATE 1')
        scope.write('*WAI')

        axq[1][0].clear()
    
        good=0
        while(good==0):
            try:
                scope.write('DATA:SOU CH1')
                scope.write('DATA:START 0')
                scope.write('DATA:STOP 5000')
                scope.write('DATA:WIDTH 2')
                scope.write('DATA:ENC RPB')
                scope.write('WFMOUTPRE:BYT_NR 2')
                ymult1 = float(scope.query('WFMPRE:YMULT?'))
                yzero1 = float(scope.query('WFMPRE:YZERO?'))
                yoff1 = float(scope.query('WFMPRE:YOFF?'))
                xincr1 = float(scope.query('WFMPRE:XINCR?'))
                scope.write('CURVE?')
                data1 = scope.read_raw()
                
                good = 1
            except:
                good = 0
        headerlen = 2 + int(data1[1])
        header = data1[:headerlen]
        ADC_wave1 = data1[headerlen:-1]
        CH1 = []
        Tq = []
        for i in range(0,len(ADC_wave1),2):
            CH1.append(256*ADC_wave1[i]+ADC_wave1[i+1])
            Tq.append(i/2)    
        Vq = np.multiply(np.subtract(CH1,CH1[0]),ymult1)

        BL = sum(Vq[0:50])/50.0
        Vq = np.subtract(Vq,BL)
        for i in range(0,len(Vq)):
            if(Vq[i]>0): Vq[i] = 0
        axq[1][0].grid(color='lightgray',linestyle='-',linewidth=1)
        axq[1][0].set_xlabel("Time (nSec)")
        axq[1][0].set_ylabel("Voltage") 
        Integral = abs(sum(Vq)*xincr1*1000000000)
        Ihist.append(Integral)
        Q = abs(sum(Vq)*xincr1*2e7)
        Qhist.append(Q)
        line = str(j)+","+str(N)+","+str(Vp[j])+","+str(round(Integral,3))+","+str(round(Q,4))+"\n"
        f.write(line)
        Qavg = sum(Qhist)/len(Qhist)
        Iavg = sum(Ihist)/len(Ihist)
        axq[1][0].plot(Tq,Vq)
        axq[1][0].text(0.6, 0.93, 'N:'+str(N),
                transform=axq[1][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        axq[1][0].text(0.6, 0.85, 'Qavg:'+str(round(Qavg,4))+"nC",
                transform=axq[1][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        axq[1][0].text(0.6, 0.77, 'Qlast:'+str(round(Q,4))+"nC",
                transform=axq[1][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        axq[1][0].text(0.6, 0.65, 'Iavg:'+str(round(Iavg,3))+"nVS",
                transform=axq[1][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)   
        axq[1][0].text(0.6, 0.57, 'Ilast:'+str(round(Integral,3))+"nVS",
                transform=axq[1][0].transAxes, fontsize=12,verticalalignment='top', bbox=props)      
        plt.pause(0.1)
    Qict.append(Qavg)
    Iict.append(Iavg)
    axq[1][1].clear()
    axq[1][1].plot(Vict,Qict,'-o',markersize=4)
    axq[1][1].grid(color='lightgray',linestyle='-',linewidth=1)
    axq[1][1].set_xlabel("Pulser Amplitude (Volts)")
    axq[1][1].set_ylabel("ICT Output Charge (nC)") 
    plt.pause(0.1)
    
    Ratio = np.divide(Qtest[0:len(Qict)],Qict)
    FitCoef = np.corrcoef(Qtest[0:len(Qict)],Qict)
    axr[0].clear()
    axr[0].plot(Qict,Qtest[0:len(Qict)],'-o',markersize=6)
    axr[0].grid(color='lightgray',linestyle='-',linewidth=1)
    axr[0].set_xlabel("ICT Output Charge (nC)")
    axr[0].set_ylabel("ICT Test Charge (nC)")
    if(len(Qict)>2):
        pfit = np.polyfit(Qict,Qtest[0:len(Qict)],1)
        axr[0].text(0.6, 0.93, 'Slope:'+str(round(pfit[0],1)),
            transform=axr[0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        axr[0].text(0.6, 0.85, 'Intercept:'+str(round(pfit[1],2)),
            transform=axr[0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
        axr[0].text(0.6, 0.77, 'Correlation:'+str(round(FitCoef[0][1],3)),
            transform=axr[0].transAxes, fontsize=12,verticalalignment='top', bbox=props)
    axr[1].clear()
    axr[1].plot(Qtest[0:len(Qict)],Ratio,'-o',markersize=6)
    axr[1].grid(color='lightgray',linestyle='-',linewidth=1)
    axr[1].set_xlabel("ICT Output Charge (nC)")
    axr[1].set_ylabel("Ratio Qtest/Qict")
    plt.pause(0.1)
print(Ratio)
print(Qict)
print(Iict)
print(Vtest)
print(Itest)
print(Qtest)
f = open(fname+".txt","w")
for k in range(0,len(Qict)):
    line = str(round(Vtest[k],2))+','+str(round(Itest[k],4))+','+str(round(Qtest[k],4))+','+str(round(Iict[k],4))+','+str(round(Qict[k],4))+','+str(round(Ratio[k],2))+'\n'
    print(k,line)
    f.write(line)

fq.savefig(fname+'RatioTestPulseQ.png')
fq.savefig(fname+'RatioIctQ.png')
plt.show(block=True)
