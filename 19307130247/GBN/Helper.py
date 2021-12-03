# ***************************
# 辅助函数
# 主要功能：封装数据报
# ***************************


class Helper(object):
    def __init__(self, data, is_ack, seq=0, is_send=0):
        self.data = data.decode()   # 报文数据
        self.is_ack = str(is_ack)   # 报文类型，如果是ack则为1，否则为0
        self.seq = str(seq)         # 报文序列号
        self.is_send = is_send      # 报文状态，如果已发送则为1，否则为0

    def __str__(self):
        return self.seq + "," + self.is_ack + "," + self.data   # 构造报文

