"""
Subclass of TimeTagger.CustomMeasurement() class for counting the
histogram of coincidence order from time tags.

Author:
starek.robert@gmail.com
"""

import numpy as np
import numba
import TimeTagger

# Timetagger format
TAGFORMAT = np.dtype([
    ('type', np.dtype('<u4')),
    ('overflow', np.dtype('<u4')),
    ('channel', np.dtype('<i4')),
    ('time', np.dtype('int64'))
])

HAMMING_LUT = np.array([bin(i).count("1")
                        for i in range(2**8)], dtype=np.uint8)
MAX_CHAN = 18  # maximum number of hardware channels
BLANK_CONST = -99  # id for channel not in the list of the applied channels


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


class CustomCoincidenceOrder(TimeTagger.CustomMeasurement):
    """
    Custom measurement class for on-the-fly counting histogram of coincidence order.
    Warning: it does not support big virtual delays between channel because the 
    coincidence tag should always come in chronological order.
    """

    def __init__(self, tagger, channels, binwidth=1000):
        TimeTagger.CustomMeasurement.__init__(self, tagger)
        self.n_channels = len(channels)
        self.binwidth = binwidth
        # The method register_channel(channel) activates
        # that data from the respective channels is transferred
        # from the Time Tagger to the PC.
        self.channels = channels

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
        self.coincidence_registers = np.zeros(self.n_channels, dtype=np.uint32)
        self.t0s = np.zeros(self.n_channels, dtype=np.int64)
        self.t1s = np.zeros(self.n_channels, dtype=np.int64)
        self.valids = np.zeros(self.n_channels, dtype=bool)
        self.histogram = np.zeros(self.n_channels+1, dtype=np.uint32)
        self.coincidence_registers_filtered = 0
        self.closed = 0
        self.last_timestamp = 0

    def on_start(self):
        # The lock is already acquired within the backend.
        pass

    def on_stop(self):
        # The lock is already acquired within the backend.
        # here maybe flush the last tag
        last_virtual_timestamp = np.array(
            [(0, 0, self.channels[0], self.last_timestamp+10*self.binwidth)], dtype=TAGFORMAT)
        CustomCoincidenceOrder.fast_process(
            last_virtual_timestamp,
            self.binwidth,
            self.n_channels,
            self.coincidence_registers,
            self.t0s,
            self.t1s,
            self.valids,
            self.histogram,
            self.coincidence_registers_filtered,
            self.closed,
            self.channels)

    @staticmethod
    @numba.jit(nopython=True, nogil=True)
    def fast_process(tags, binwidth, channels,
                     coincidence_registers, t0s, t1s, valids,
                     histogram, coincidence_registers_filtered,
                     closed, channels_list
                     ):
        """
        A precompiled version of the histogram algorithm for better performance
        nopython=True: Only a subset of the python syntax is supported.
                       Avoid everything but primitives and numpy arrays.
                       All slow operation will yield an exception
        nogil=True:    This method will release the global interpreter lock. So
                       this method can run in parallel with other python code

        Warning: it mutates passed arrays.

        Args:
            TAGFORMAT: ndarray of tagformat dtype holding timestamps
            coincidence_registers : uint32 ndarray holding coincidence marks
            t0s, t1s : int64 ndarray holding register times
            valids : bool ndarray
            histogram : uint32 ndarray
            coincidence_registers_filtered : int32
            closed : int32
        Returns:
            last processed time stamp
        """
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
            coincidence_registers_filtered = 0
            closed = 0
            for j in range(channels):
                if (t0s[j] < timestamp < t1s[j]) and channel_id != j and valids[j]:
                    coincidence_registers[j] = coincidence_registers[j] | (
                        1 << channel_id)
                if timestamp > t1s[j] and valids[j]:
                    closed += 1
                    coincidence_registers_filtered = \
                        coincidence_registers_filtered | \
                        coincidence_registers[j]
                    coincidence_registers[j] = 0
                    valids[j] = False
            if closed > 0:
                idx = numba_ham32(coincidence_registers_filtered)
                if idx > 0:
                    histogram[idx] += 1
            t0s[channel_id] = timestamp
            t1s[channel_id] = timestamp + binwidth
            coincidence_registers[channel_id] = (1 << channel_id)
            valids[channel_id] = True
        return timestamp

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
        self.last_timestamp = CustomCoincidenceOrder.fast_process(
            incoming_tags,
            self.binwidth,
            self.n_channels,
            self.coincidence_registers,
            self.t0s,
            self.t1s,
            self.valids,
            self.histogram,
            self.coincidence_registers_filtered,
            self.closed,
            self.channels)


if __name__ == '__main__':
    tagger = TimeTagger.createTimeTagger()
    # play there with settings to test the coincidence-order counting
    #tagger.setTestSignal([1, 2, 3, 4], True)
    tagger.setTestSignal([1, 3, 4], True)
    # delay the stop channel by 2 ns to make sure it is later than the start
    tagger.setInputDelay(2, 50)
    tagger.setInputDelay(3, 100)
    tagger.setInputDelay(4, 150)
    CC_WINDOW = 500  # ps
    CC_CHANNELS = [1, 2, 3, 4]
    TEST_DURATION = int(1e12)
    # We first have to create a SynchronizedMeasurements object to synchronize several measurements
    with TimeTagger.SynchronizedMeasurements(tagger) as measurementGroup:
        cc_meas = CustomCoincidenceOrder(
            measurementGroup.getTagger(), CC_CHANNELS, CC_WINDOW)
        rate_meas = TimeTagger.Counter(
            measurementGroup.getTagger(), CC_CHANNELS, 1e12, int(TEST_DURATION//1e12))
        measurementGroup.startFor(TEST_DURATION)
        measurementGroup.waitUntilFinished()
        index = cc_meas.getIndex()
        coincidences = cc_meas.getData()
        rate = rate_meas.getData()

    TimeTagger.freeTimeTagger(tagger)
    print("Coincidence order")
    print(index)
    print("counts on channels")
    print(coincidences)
    print("Total:", np.sum(rate))
