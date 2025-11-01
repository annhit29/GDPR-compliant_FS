import sys

def count_lines(fn): 
    with open(fn) as f:
        lines = f.readlines()
    b, j, is_sp, sp = False, 0, False, 0 
    m = 0
    total, sp_total = 0, 0
    for i in range(len(lines)):
        if lines[i].replace(" ", "") == "\n" \
           or lines[i].replace(" ", "").startswith("#") \
           or lines[i].startswith("import") \
           or lines[i].startswith("from"):
            m += 1
        elif lines[i][0] != " " and lines[i][0] != "\t":
            if b and not is_sp:
                total += i - j - m - sp
                sp_total += sp
            if b and is_sp:
                sp_total += i - j - m
            print(f"{i-j-m} lines")
            if lines[i].endswith("#sp\n"):
                b = True
                j = i
                m = 0
                is_sp = True
                sp = 0
                print(f"S: {lines[i][:-1]}", end=" ")
            elif lines[i].endswith("#nc\n") or lines[i].startswith("\"\"\""):
                b = False
                j = i
                m = 0
                is_sp = False
                sp = 0
                print(f"N: {lines[i][:-1]}", end=" ")
            else:
                b = True
                j = i
                m = 0
                is_sp = False
                sp = 0
                print(f"Y: {lines[i][:-1]}", end=" ")
        elif lines[i].endswith("#sp\n"):
            sp += 1
    if b and not is_sp:
        total += len(lines)- j - m - sp
        sp_total += sp
    if b and is_sp:
        sp_total += len(lines) - j - m
    print(f"{len(lines)-j-m} lines")
    print(f"Total: {total} lines")
    print(f"Special: {sp_total} lines")

if __name__ == '__main__':

    assert(len(sys.argv) > 1)
    
    count_lines(sys.argv[1])
    
