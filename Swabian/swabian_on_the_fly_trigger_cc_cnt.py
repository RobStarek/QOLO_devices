"""
Module for counting coincidence order from Timettagger data.
The timestamps are loaded from file saved with older style tagger.Dump().
We assume that delays are already compensated and that the used channels
are sequential like 1,2,...,n with no gaps.

starek.robert@gmail.com
"""

import numpy as np
import numba as nb
#import timeit

# Timetagger format
TAGFORMAT = np.dtype([
    ('overflow', np.dtype('<u4')),
    ('channel', np.dtype('<i4')),
    ('time', np.dtype('int64'))
])

# constant 8-bit (256 lines) LUT for Hamming weight
HAMMING_LUT = np.array([bin(i).count("1")
                        for i in range(2**8)], dtype=np.uint8)


@nb.jit(nopython=True)
def numba_ham32(i):
    """Hamming weight of 32-bit integer."""
    # 32 integer hamming weight
    bitcount = HAMMING_LUT[i & 0xff]  # 0-7
    i = (i >> 8)
    bitcount += HAMMING_LUT[i & 0xff]  # 8-15
    i = (i >> 8)
    bitcount += HAMMING_LUT[i & 0xff]  # 16-23
    i = (i >> 8)
    bitcount += HAMMING_LUT[i & 0xff]  # 24-31
    return bitcount


@nb.jit(nopython=True)
def _nb_make_histogram(tc_array, binwidth, channels,
                       coincidence_registers, t0s, t1s, valids,
                       histogram, coincidence_registers_filtered,
                       closed
                       ):
    """
    Build coincidence order histogram from
    timestamps. To be used from make_histogram().

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
        None
    """
    for element in tc_array:
        timestamp = element['time']
        channel_id = element['channel'] - 1
        ovf = element['overflow']
        if ovf > 0:
            continue
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
    return 0

@nb.jit(nopython=True)
def _nb_make_cp_histogram(tc_array, binwidth, channels,
                       coincidence_registers, t0s, t1s, valids,
                       histogram, coincidence_registers_filtered,
                       closed
                       ):
    """
    Build coincidence pattern histogram from
    timestamps. To be used from make_pattern_histogram().

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
        None
    """
    for element in tc_array:
        timestamp = element['time']
        channel_id = element['channel'] - 1
        ovf = element['overflow']
        if ovf > 0:
            continue
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
            idx = coincidence_registers_filtered
            if idx > 0:
                histogram[idx] += 1
        t0s[channel_id] = timestamp
        t1s[channel_id] = timestamp + binwidth
        coincidence_registers[channel_id] = (1 << channel_id)
        valids[channel_id] = True
    return 0

def make_histogram(tc_iterable, binwidth, channels):
    """
    Build coincidence-order histogram from timestamp data.

    Args:
        tc_iterable : object capable of iterating throughs chunks of
          TAGFORMATh yielded element should be ndarray of tagformat dtype.
        binwidth : window length in the timestamp units
        channels : number of detection channels
    Returns:
        histogram (ndarray, uint32)
    """
    coincidence_registers = np.zeros(channels, dtype=np.uint32)
    t0s = np.zeros(channels, dtype=TAGFORMAT['time'])
    t1s = np.zeros(channels, dtype=TAGFORMAT['time'])
    valids = np.zeros(channels, dtype=bool)
    histogram = np.zeros(channels+1, dtype=np.uint32)
    coincidence_registers_filtered = 0
    closed = 0
    # iterate through array chunks
    i = -1
    for i, data_chunk in enumerate(tc_iterable):
        _nb_make_histogram(data_chunk, binwidth, channels, coincidence_registers, t0s,
                           t1s, valids, histogram, coincidence_registers_filtered, closed)
    # at the end, flush the results using virtual tag
    if i > -1:
        data_chunk_end = np.array(
            [(0, 1, data_chunk[-1]['time']+10*binwidth)], dtype=TAGFORMAT)
        _nb_make_histogram(data_chunk_end, binwidth, channels, coincidence_registers, t0s,
                        t1s, valids, histogram, coincidence_registers_filtered, closed)
    return histogram

def make_pattern_histogram(tc_iterable, binwidth, channels):
    """
    Build coincidence-pattern histogram from timestamp data.
    Args:
        tc_iterable : object capable of iterating throughs chunks of
          TAGFORMATh yielded element should be ndarray of tagformat dtype.
        binwidth : window length in the timestamp units
        channels : number of detection channels
    Returns:
        histogram (ndarray, uint32)
    """
    coincidence_registers = np.zeros(channels, dtype=np.uint32)
    t0s = np.zeros(channels, dtype=TAGFORMAT['time'])
    t1s = np.zeros(channels, dtype=TAGFORMAT['time'])
    valids = np.zeros(channels, dtype=bool)
    histogram = np.zeros(2**channels, dtype=np.uint32)
    coincidence_registers_filtered = 0
    closed = 0

    # iterate through array chunks
    i = -1
    for i, data_chunk in enumerate(tc_iterable):
        _nb_make_cp_histogram(data_chunk, binwidth, channels, coincidence_registers, t0s,
                           t1s, valids, histogram, coincidence_registers_filtered, closed)
    # at the end, flush the results using virtual tag
    if i > -1:
        data_chunk_end = np.array(
            [(0, 1, data_chunk[-1]['time']+10*binwidth)], dtype=TAGFORMAT)
        _nb_make_cp_histogram(data_chunk_end, binwidth, channels, coincidence_registers, t0s,
                        t1s, valids, histogram, coincidence_registers_filtered, closed)
    return histogram

def get_pattern_description(channels):    
    return [format(i, f'0{channels}b') for i in range(1 << channels)]


def iterate_chunks(fn, chunk_size = 1024):
    n_bytes = int(chunk_size * TAGFORMAT.itemsize)
    with open(fn, 'rb') as tagfile:
        end_byte = tagfile.seek(0, 2)
        i = tagfile.seek(0, 0)
        print(end_byte)
        while i < end_byte:
            print(i//n_bytes)
            data_buffer = tagfile.read(n_bytes)
            data = np.frombuffer(data_buffer, dtype=TAGFORMAT)
            i = tagfile.tell()
            yield data

def iterate_chunks_filereader(file_reader_object, chunksize=1024):   
    while file_reader_object.hasData():
        data = file_reader_object.getData(chunksize)      
        actual_chunksize = data.size
        chunk = np.empty((actual_chunksize,), dtype = TAGFORMAT)
        chunk['overflow'] = data.getOverflows()
        chunk['time'] = data.getTimestamps()
        chunk['channel'] = data.getChannels()
        yield chunk
        
if __name__ == '__main__':    
    fn = "myfile.dat"
    chunk_generator = iterate_chunks(fn, 2*1024*1024)
    histogram = make_histogram(chunk_generator, 1000, 4)
    print(histogram)
