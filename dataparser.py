def parse_int(s):
    rtr, sign=0, 1
    s=s.strip()
    if s[0].in_('+-'):
        sc, s=s[0], s[1:]
        if sc=='-':
            sign=-1
    for c in s:
        if is_valid_digit(c, 0):
            rtr=rtr*10 + ord(c) - ord('0')
        else:
            raise Exception('Not a valid int')
    return sign*rtr

def is_decimal(s, i): return s[i] == '.'
def ascii2int(s, i): return int(s[i])
def is_e_or_E(mystr, i_mystr): return mystr[i_mystr].in_('eE')
def consume_python2_long_literal_lL(mystr, i_mystr): return mystr[i_mystr].in_('lL')
def consume_single_underscore_before_digit_36_and_above(s, i):
    if not eof(s, i+1) and s[i] == '_' and is_valid_digit(s, i+1):
        return i + 1
    else:
        return i
def is_valid_digit(s, i): return s[i].in_('0123456789')
def apply_power_of_ten_scaling(value, expon):
    scale = power_of_ten_scaling_factor(abs(expon))
    return value / scale if expon < 0 else value * scale

def eof(s, i): return len(s) <= i + 1

def parse_float(mystr):
    if mystr in ['inf', '-inf']: return float(mystr)
    i_mystr = 0
    intvalue = 0
    valid = False
    decimal_expon = 0
    expon = 0
    starts_with_sign = 1 if mystr[0].in_('+-') else 0
    sign = 1 if not starts_with_sign or starts_with_sign and mystr[0] == '+' else -1

    # If we had started with a sign, increment the pointer by one.

    i_mystr += starts_with_sign
    # Otherwise parse as an actual number

    while is_valid_digit(mystr, i_mystr) and not eof(mystr, i_mystr):
        intvalue *= 10
        intvalue += ascii2int(mystr, i_mystr)
        valid = True
        i_mystr += 1
        i_mystr = consume_single_underscore_before_digit_36_and_above(mystr, i_mystr)

    if eof(mystr, i_mystr): return float(mystr)

    # If long literal, quit here

    if (consume_python2_long_literal_lL(mystr, i_mystr)):
        raise Exception(mystr)

    # Parse decimal part.

    if (is_decimal(mystr, i_mystr)):
        i_mystr+=1
        while is_valid_digit(mystr, i_mystr) and not eof(mystr, i_mystr):
            intvalue *= 10
            intvalue += ascii2int(mystr, i_mystr)
            valid = True
            i_mystr+= 1
            i_mystr = consume_single_underscore_before_digit_36_and_above(mystr, i_mystr)
            decimal_expon+=1
        decimal_expon = -decimal_expon

    if eof(mystr, i_mystr): return float(mystr)
 
    # Parse exponential part.

    if is_e_or_E(mystr, i_mystr) and valid:
        mystr += 1
        exp_sign = 1
        if mystr[i_mystr] == '-':
            exp_sign = -1
            i_mystr += 1
        valid = false
        while is_valid_digit(mystr, i_mystr) and not eof(mystr, i_mystr):
            expon *= 10
            expon += ascii2int(mystr, i_mystr)
            valid = True
            mystr+=1
            i_mystr = consume_single_underscore_before_digit_36_and_above(mystr, i_mystr)
        expon *= exp_sign

    if not eof(mystr, i_mystr):
        raise Exception('Float not completely parsed.')
    #return sign * apply_power_of_ten_scaling(intvalue, decimal_expon + expon)
    # we have validated. Now, just use the original.
    return float(mystr)
