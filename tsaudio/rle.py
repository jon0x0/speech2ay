def encode(data):
    out=bytearray();i=0
    while i<len(data):
        j=i+1
        while j<len(data) and data[j]==data[i] and j-i<255:j+=1
        out.extend((j-i,data[i]));i=j
    return bytes(out)+b'\0'
