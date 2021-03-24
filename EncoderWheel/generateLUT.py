
def extract_bit(i,n):
    m = 0b1 << n
    return ((i & m) >> n)

def bits_to_grey(i):
    left = (i >> 1) + (0b1000 & i)
    right = i & 0b0111
    return (left ^ right)



li = ', '.join([f'0b{bits_to_grey(i):04b}' for i in range(16)])


minimum = 1000
maximum = 1900
mylist = [minimum]*16
da = 90/15

for i in range(16):
    idx = bits_to_grey(i)
    dur = int(maximum - (maximum-minimum)*(i/15))
    mylist[idx] = dur
    print(f'{i:02d}  {i:04b}  {bits_to_grey(i):04b}  {dur}  {da*i:.1f}')


inner = ', '.join([f'{el:d}' for el in mylist])
codestr = f"int PWLUT[16] = {{{inner}}};\n"
print(codestr)

    

