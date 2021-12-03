import re

if __name__ == '__main__':
    msg = '123,2,Once when I was six years old I saw a magnificent picture in a book, called True Stories from Nature, about the primeval forest. It was a picture of a boa constrictor in the act of swallowing an animal. Here is a copy of the drawing.'
    list = re.split(r'\W', msg, 2)
    print(list)
    seq = list[0]
    ack = list[1]
    dat = list[2]
    print(seq,ack,dat)
