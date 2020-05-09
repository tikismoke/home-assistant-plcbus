import serial                    # import pySerial module
import time
from binascii import hexlify

ComPort = serial.Serial('/dev/ttyUSB0',9600) # open the COM Port
cmdplcbus = {
b'00': 'ALL_UNITS_OFF',
b'01': 'ALL_LIGHTS_ON',
b'02': 'ON',
b'03': 'OFF',
b'22': 'ON', #ON and ask to send ACK (instead of '02')
b'23': 'OFF', #OFF and send ACK
b'24': 'DIM',
b'25': 'BRIGHT',
b'06': 'ALL_LIGHTS_OFF',
b'07': 'ALL_USER_LTS_ON',
b'08': 'ALL_USER_UNIT_OFF',
b'09': 'ALL_USER_LIGHT_OFF',
b'2a': 'BLINK',
b'2b': 'FADE_STOP',
b'2c': 'PRESET_DIM',
b'0d': 'STATUS_ON',
b'0e': 'STATUS_OFF',
b'0f': 'STATUS_REQUEST',
b'30': 'REC_MASTER_ADD_SETUP',
b'31': 'TRA_MASTER_ADD_SETUP',
b'12': 'SCENE_ADR_SETUP',
b'13': 'SCENE_ADR_ERASE',
b'34': 'ALL_SCENES_ADD_ERASE',
b'15': 'FOR FUTURE',
b'16': 'FOR FUTURE',
b'17': 'FOR FUTURE',
b'18': 'GET_SIGNAL_STRENGTH',
b'19': 'GET_NOISE_STRENGTH',
b'1a': 'REPORT_SIGNAL_STREN',
b'1b': 'REPORT_NOISE_STREN',
b'1c': 'GET_ALL_ID_PULSE',
b'1d': 'GET_ALL_ON_ID_PULSE',
b'1e': 'REPORT_ALL_ID_PULSE',
b'1f': 'REPORT_ONLY_ON_PULSE'}
home = "ABCDEFGHIJKLMNOP"

while True:
    if ComPort.inWaiting() < 9:
        time.sleep(0.4)
#    return
    while ComPort.inWaiting() >= 9:
        message = ComPort.read(9) #wait for max 400ms if nothing to read
#        except IOError:
#            pass
        if(message):
            m_string = hexlify(message)
        #self.explicit_message(m_string)
        #if message is likely to be an answer, put it in the right queue
        #First we check that the message is not from the adapter itself
        #And simply ignore it if it's the case 
            print("message : %s" % m_string)
            r = {}
            r["start_bit"] =  m_string[0:2]
            r["data_length"] = int(m_string[2:4])
            int_length = int(m_string[2:4])*2
            r["data"] =  m_string[4:4 + int_length]
            r["d_user_code"] = r["data"][0:2]
            r["d_home_unit"] = "%s%s" % (home[int(r["data"][2:3], 16)],int(r["data"][3:4], 16)+1)
            r["d_command"] =  cmdplcbus[r["data"][4:6]]
#            r["d_data1"] =  int(r["data"][6:8],16)
#            r["d_data2"] =  int(r["data"][8:10],16)
            r["d_data1"] =  r["data"][6:8]
            r["d_data2"] =  r["data"][8:10]
            if r["data_length"] == 6:
                r["rx_tw_switch"] = r["data"][11:]
            r["end_bit"] =  m_string[-2:]
            if r["rx_tw_switch"] == b'0':
                print(r)
            if r["rx_tw_switch"] == b'c':
                print("status?",r)
            if r["d_command"] == "GET_ALL_ON_ID_PULSE":
                print ("A détaillé")
                data = int(r["data"][6:10], 16)
                #data = "%s%s" % (bin(r["d_data1"])[2:].zfill(8), bin(r["d_data2"])[2:].zfill(8))
                #data = "%s%s" % r["d_data1"], r["d_data2"]
                print (data)
                for i in range(0, 16):
                    if data >> i & 1:
                        print (i)

                #for c in data:
                    #unit = c
                    #print (unit)
ComPort.close()
