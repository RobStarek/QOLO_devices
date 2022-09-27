"""
Subclass of TimeTagger.CustomMeasurement() class for counting the
histogram of coincidence order from time tags.
"""

import numpy as np
import numba
import TimeTagger

#set this to true if the we want to create an artificial SW start trigger signal
#and allow sensing tags even before first real trigger timestamp is registered
OPT_TRIG_1ST_SW = True 

# Timetagger format
TAGFORMAT = np.dtype([
    ('type', np.dtype('<u4')),
    ('overflow', np.dtype('<u4')),
    ('channel', np.dtype('<i4')),
    ('time', np.dtype('int64'))
])

HAMMING_LUT = np.array([bin(i).count("1")
                        for i in range(2**8)], dtype=np.uint8)
@numba.jit(nopython=True)
def numba_ham32(i):
    """Hamming weight (number of set bits) of 32-bit integer."""
    # 32 integer hamming weight
    bitcount = HAMMING_LUT[i & 0xff]  # 0-7
    i = (i >> 8)
    bitcount += HAMMING_LUT[i & 0xff]  # 8-15
    i = (i >> 8)
    bitcount += HAMMING_LUT[i & 0xff]  # 16-23
    i = (i >> 8)
    bitcount += HAMMING_LUT[i & 0xff]  # 24-31
    return bitcount


class CustomTrigCoincidenceOrder(TimeTagger.CustomMeasurement):
    """
    Custom measurement class for on-the-fly counting histogram of coincidence order.
    Warning: it does not support big virtual delays between channel because the
    coincidence tag should always come in chronological order.
    """

    def __init__(self, tagger, trig_channel, channels, binwidth=1000):
        """
        Args:
            tagger : timetagger instance
            trigger_c : channel number of trigger
            channels : list of channel numbers
        """
        TimeTagger.CustomMeasurement.__init__(self, tagger)
        self.n_channels = len(channels)
        self.binwidth = binwidth
        # The method register_channel(channel) activates
        # that data from the respective channels is transferred
        # from the Time Tagger to the PC.
        self.channels = channels
        if trig_channel not in channels:
            raise ValueError
        self.trig_channel = trig_channel

        for channel_number in channels:
            self.register_channel(channel=channel_number)

        self.clear_impl()

        # At the end of a CustomMeasurement construction,
        # we must indicate that we have finished.
        self.finalize_init()

    def __del__(self):
        # The measurement must be stopped before deconstruction to avoid
        # concurrent process() calls.
        self.stop()

    def getData(self):
        # Acquire a lock this instance to guarantee that process() is not running in parallel
        # This ensures to return a consistent data.
        with self.mutex:
            return self.histogram.copy()

    def getIndex(self):
        # This method does not depend on the internal state, so there is no
        # need for a lock.
        arr = np.arange(0, self.n_channels+1)
        return arr

    def clear_impl(self):
        # The lock is already acquired within the backend.
        self.coincidence_register = np.uint32(0)
        self.t0 = np.int64(0)
        self.t1 = np.int64(0)
        self.valid = False
        self.histogram = np.zeros(self.n_channels+1, dtype=np.uint32)
        self.last_timestamp = np.int64(0)

    def on_start(self):
        # The lock is already acquired within the backend.
        # start trigger by a virtual first trigger
        if OPT_TRIG_1ST_SW:
            first_virtual_timestamp = np.array(
                [(0, 0, self.trig_channel, 0)], dtype=TAGFORMAT)
            self.last_timestamp, self.t0, self.t1, self.coincidence_register, self.valid =\
                CustomTrigCoincidenceOrder.fast_process(
                    first_virtual_timestamp,
                    self.trig_channel,
                    self.binwidth,
                    self.coincidence_register,
                    self.t0,
                    self.t1,
                    self.valid,
                    self.histogram,
                    self.channels)
            self.histogram[1] = self.histogram[1] - 1

    def on_stop(self):
        # The lock is already acquired within the backend.
        # here maybe flush the last tag
        last_virtual_timestamp = np.array(
            [(0, 0, self.trig_channel, self.last_timestamp+10*self.binwidth)], dtype=TAGFORMAT)
        CustomTrigCoincidenceOrder.fast_process(
            last_virtual_timestamp,
            self.trig_channel,
            self.binwidth,
            self.coincidence_register,
            self.t0,
            self.t1,
            self.valid,
            self.histogram,
            self.channels)

    @staticmethod
    @numba.jit(nopython=True, nogil=True)
    def fast_process(tags, trig_channel, binwidth,
                     coincidence_register, t0, t1, valid,
                     histogram,
                     channels_list
                     ):
        """
        Warning: it mutates the numpy arrays.
        Args:
            TAGFORMAT: ndarray of tagformat dtype holding timestamps
            trig_channel : int
            binwiddth: int
            channels : list
            coincidence_register : uint32
            t0, t1 : int64
            valids : bool ndarray
            histogram : uint32 ndarray    
        Returns:
            last timestamp, t0, t1, coincidence_register, valid
        """
        trigger_channel_id = channels_list.index(trig_channel)
        for tag in tags:
            # tag.type can be: 0 - TimeTag, 1- Error, 2 - OverflowBegin, 3 -
            # OverflowEnd, 4 - MissedEvents
            if tag['type'] != 0:
                continue
            timestamp = tag['time']
            channel_num = tag['channel']
            # there has to be a better way, maybe lookup table?
            # or dynamically precompile mapping function?
            if channel_num in channels_list:
                channel_id = channels_list.index(channel_num)
            else:
                continue
            timestamp = tag['time']

            if (channel_id == trigger_channel_id):
                if valid:
                    # in the beginning of new cc window, update histogram
                    #
                    idx = numba_ham32(coincidence_register)                    
                    histogram[idx] += 1
                else:
                    valid = True
                # update registers
                t0 = timestamp
                t1 = timestamp + binwidth
                coincidence_register = (1 << trigger_channel_id)
            elif (t0 < timestamp <= t1) and valid:
                coincidence_register = coincidence_register | (1 << channel_id)
            elif timestamp > t1 and valid:
                # count timestamps outside valid cc window
                histogram[0] += 1

        return timestamp, t0, t1, coincidence_register, valid

    def process(self, incoming_tags, begin_time, end_time):
        """
        Main processing method for the incoming raw time-tags.

        The lock is already acquired within the backend.
        self.data is provided as reference, so it must not be accessed
        anywhere else without locking the mutex.

        Parameters
        ----------
        incoming_tags
            The incoming raw time tag stream provided as a read-only reference.
            The storage will be deallocated after this call, so you must not store a reference to
            this object. Make a copy instead.
            Please note that the time tag stream of all channels is passed to the process method,
            not only the ones from register_channel(...).
        begin_time
            Begin timestamp of the of the current data block.
        end_time
            End timestamp of the of the current data block.
        """
        self.last_timestamp, self.t0, self.t1, self.coincidence_register, self.valid =\
            CustomTrigCoincidenceOrder.fast_process(
                incoming_tags,
                self.trig_channel,
                self.binwidth,
                self.coincidence_register,
                self.t0,
                self.t1,
                self.valid,
                self.histogram,
                self.channels
            )


#Basic examples
if __name__ == '__main__':
    tagger = TimeTagger.createTimeTagger()
    #tagger.setTestSignalDivider(74) #default 0.85 MHz
    tagger.setTestSignalDivider(37) #1.7 MHz per channel x4 = 6.8 Mtags/sec
    #theoretical (advertised maximum rate 8.5 M tags/s, i.e. 1 M tags per channel)

    # play there with settings to test the coincidence-order counting
    CC_WINDOW = 1000  # ps
    CC_CHANNELS = [1, 2, 3, 4]
    TRIG = 1
    TEST_DURATION = int(1e12)    
    #test configurations (active channel, delay dict, dividers dict)    
    confs = {
        'just_trigger' : (
            [1], #active channels
            {2 : int(CC_WINDOW//2)}, #software delays
            {}, #event dividers
            ),
        'singles' : (
            [1, 2],
            {2 : int(CC_WINDOW//2)}, 
            {} 
            ),
        'doubles' : (
            [1, 2, 3],
            {2 : int(CC_WINDOW//2), 3 : 10+int(CC_WINDOW//2)},
            {},
            ),
        'triples' : (
            [1, 2, 3, 4],
            {2 : int(CC_WINDOW//2), 3 : 10+int(CC_WINDOW//2), 4: 20+int(CC_WINDOW//2)},
            {}
            ),
        'singles_outside' : (
            [1, 2],
            {2 : int(2*CC_WINDOW)},
            {} 
            ),
        'singles_at_edge' : (
            [1, 2],
            {2 : int(125+CC_WINDOW)},
            {} 
            ),
        'every_second_single' : (
            [1, 2],
            {2 : int(CC_WINDOW//2)},
            {2 : 2} 
            ),     
        'pyramid' : (
            [1, 2, 3, 4],
            {2 : int(CC_WINDOW//2), 3 : int(100+CC_WINDOW//2), 4 : int(200+CC_WINDOW//2)},
            {1 : 1, 2 : 2, 3 : 3, 4 : 4} 
            ),                         
        'no_trigger' : ([2], {2 : 100} ),
    }
    CONF = 'triples'
    test_chans, delay_dict, divider_dict = confs.get(CONF)
    tagger.setTestSignal(test_chans, True)    
    for chan, delay in delay_dict.items():
        tagger.setDelaySoftware(chan, delay)
    
    for chan, divider in divider_dict.items():
        tagger.setEventDivider(chan, int(divider))


    # We first have to create a SynchronizedMeasurements object to synchronize several measurements
    with TimeTagger.SynchronizedMeasurements(tagger) as measurementGroup:
        cc_meas = CustomTrigCoincidenceOrder(
            measurementGroup.getTagger(), TRIG, CC_CHANNELS, CC_WINDOW)
        rate_meas = TimeTagger.Counter(
            measurementGroup.getTagger(), CC_CHANNELS, 1e12, int(TEST_DURATION//1e12))
        measurementGroup.startFor(TEST_DURATION)
        measurementGroup.waitUntilFinished()
        index = cc_meas.getIndex()
        coincidences = cc_meas.getData()
        rate = rate_meas.getData()

    TimeTagger.freeTimeTagger(tagger)

    print(f'Configuration: {CONF}')
    print("Coincidence order")
    print(index)
    print("counts on channels")
    labels = ['outside trig', 'just trig', 'single events'] + [f'{i+2}-fold cc' for i in range(len(CC_CHANNELS) -1)]
    for i, count in enumerate(coincidences):
        print(f'{labels[i]}\t{count}')
    print("Total timestamps:", np.sum(rate))
    print(rate)
    print("Mean rate per active channel:", np.sum(rate)/len(test_chans))
