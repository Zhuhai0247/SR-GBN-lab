import select
import socket
import time
import re
from random import random
from Helper import Helper

# ***********************************************************************************
# SRServer实现：相较GBN，增加接收窗口和计时器
# 接收方
# 1.序号在 [rcv_base,rcv_base+N-1]内的分组正确接收。如果分组之前没有收到，
#   则缓存分组，如果分组序号等于rcv_base，则将该分组和分组之前缓存的分组（若有）一起交付。
# 2.序号在 [rcv_base-N,rcv_base-1]内的分组被正确收到，
#   则返回一个ACK。（ACK可能丢失，导致send_base无法移动）
# 3.他情况忽略。
# ***********************************************************************************


class SRServer:
    def __init__(self):          # 同client
        # self.base = 1           窗口开头不再需要，python可以简化地直接移动数组
        self.nextseqnum = 1     # 待发送数据下标
        self.max_time = 5       # 超时时间
        self.wait_time = 15     # 等待数据发送时间
        self.send_window = []   # 更改为发送滑动窗口

        self.fd_num = 0         # 发送包的数量
        self.N = 3              # 发送窗口大小

        self.addr = ('127.0.0.1',18888)                                 # server地址和端口
        self.client_addr = ('127.0.0.1',8888)                           # client地址和端口
        self.socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)   # socket初始化，根据报告要求，用IPv4，UDP
        self.socket.bind(self.addr)                                     # socket绑定

        # 以上为GBN原本的参数，基本不变，删除了rev_data,下面为SR增加的参数
        self.M = 3                  # 接收窗口大小
        self.receive_window = []    # 接收窗口

    def send(self,buffer):
        fd_timer = []               # 发送报文超时计时器
        data_timer = 0              # 接收报文超时计时器
        self.fd_num = len(buffer)   # 计算包的数量
        last_ack = 0
        rec_data = []               # 接收数据缓存

        while True:
            time.sleep(0.5)
            while len(self.send_window) < self.N:   # 情况1:窗口未满，将数据放入，这里为了方便，和超时数据在最后一起发送
                if self.nextseqnum > self.fd_num:   # 如果待发序列大小已经大于包数量，则break
                    break
                data = Helper(buffer[self.nextseqnum - 1],0,
                              seq=self.nextseqnum)  # 封装数据报
                self.send_window.append(data)       # 添加到窗口
                self.nextseqnum += 1                # 序列号增加
                fd_timer.append(0)                  # SR新增：开始该数据报的计时

            for index, item in enumerate(fd_timer): # 情况2：超时,SR新增：判断每一个正在计时的包是否超时
                if item > self.max_time:
                    if self.send_window[index].is_send != 2:
                        self.send_window[index].is_send = 0
                        print('server:超时！重传:',self.send_window[index].seq)

            if not self.send_window:                # 退出条件：窗口为空
                if not fd_timer and data_timer > self.wait_time:
                    with open('sreceive.txt', 'wb') as f:
                        for d in rec_data:
                            f.write(d[2:].encode())
                    print('server:发送/接收成功！')
                    break

            for index, data in enumerate(self.send_window):                  # 将情况1、2的数据都发出去
                if not data.is_send:                                         # 判断窗口内数据是否未发送
                    print('server:发送数据，序号为:',data.seq)                      # 打印信息
                    self.socket.sendto(str(data).encode(),self.client_addr)  # 发送报文
                    data.is_send = 1                                         # 将该包标记为发送但未收到ACK
                    fd_timer[index] = 0                                      # 启动该包计时器

            # 以下是client和server算法的结合
            read_fd, write_fd, error_fd = select.select([self.socket, ], [], [], 1)     # 利用select模块进行无阻塞的socket连接

            if len(read_fd) > 0:                                    # 监听到可读套接字
                msg, addr = self.socket.recvfrom(1024)              # 获取报文
                msg = msg.decode()                                  # 解码报文
                list = re.split(r'\W',msg,2)
                temp_seq = list[0]
                temp_ack = list[1]
                temp_data = list[2]
                if temp_ack == '1':                                   # 如果是ACK报文
                    ack_num = temp_seq
                    print('server:收到ACK，序号为:',temp_seq)
                    if len(self.send_window) == 0:                    # 如果不需要ACK报文，跳过
                        continue
                    if int(ack_num) < int(self.send_window[0].seq):   # 不是期望报文
                        continue
                    fd_timer[int(ack_num) - int(self.send_window[0].seq)] = 0   # 重启对应报文的计时器
                    for i in range(len(self.send_window)):
                        if ack_num == self.send_window[i].seq:                  # 如果是期待中的ACK（即接收窗口中期待的序列号）
                            self.send_window[i].is_send = 2                     # 表明该报文发送完毕
                            if i == 0:                                          # 右移发送窗口
                                index = 0
                                flag = 1
                                for index in range(len(self.send_window)):      # 从第二个开始检查
                                    if self.send_window[index].is_send != 2:
                                        flag = 0
                                        break
                                index += flag                                   # 如果没有，则index移动1位；如果有1位，则index移动2位，如果有两位，则index移动2+1=3位
                                self.send_window = self.send_window[index:]     # 发送窗口右移
                                fd_timer = fd_timer[index:]                     # 计时器窗口随之右移
                            break
                else:                                                           # 收到了数据
                    for index, item in enumerate(fd_timer):                     # 给每个超时计时器+1
                        if self.send_window[index].is_send != 2:
                            item += 1
                    print('server:收到数据，序号为: ',temp_seq)
                    ack_num = int(temp_seq)
                    data_timer = 0                                              # 接收报文计时器置零

                    if last_ack == ack_num - 1:                                 # 为期望包
                        if random() < 0.2:                                      # 模拟丢包/ACK,概率20%
                            if random() < 0.5:
                                print('server:模拟数据丢失，丢失序列号:',ack_num)
                                continue
                            else:
                                print('server:模拟ACK丢失，丢失序列号:',ack_num)
                                last_ack = ack_num                              # 更新最近的ACK
                                rec_data.insert(ack_num-1,temp_data)                  # 插入数据
                                continue
                        remove = []                                             # 记录要删除的接收窗口
                        rec_data.insert(ack_num-1,temp_data)                          # 插入数据
                        self.socket.sendto(str(Helper(''.encode(), 1, ack_num)).encode(),addr)
                        print('server:发送ACK，序号为:',ack_num)
                        self.receive_window.append(ack_num)                     # 在接收窗口记录该序列号
                        for i in range(self.M):                                 # 判断该序列号之后是否有缓存报文
                            if (ack_num + i) not in self.receive_window:
                                last_ack = ack_num + i - 1                      # 如果没有，则i=1，last_ack = ack_num
                                break
                            else:
                                last_ack = ack_num + i                          # 如果全部都有，则i=2,last_ack = ack_num + 2
                                remove.append(ack_num + i)                      # i=0时一定满足，i!=0时可能满足，满足几次append几次
                        for element in remove:
                            self.receive_window.remove(element)                 # 用删除元素来抽象化窗口右移
                    else:                                                       # 不是期望包
                        if (last_ack + 1 + self.M) > ack_num > last_ack and ack_num not in self.receive_window:             # 可缓存的包
                            self.receive_window.append(ack_num)                                                             # 记录序列号
                            rec_data.insert(ack_num-1,temp_data)                                                            # 缓存该包数据
                            print('server:缓存数据，序号为:',ack_num)
                            self.socket.sendto(str(Helper(''.encode(), 1, ack_num)).encode(),addr)                          # 发送ACK
                        elif ack_num <= last_ack:                                                                           # 是以前的包
                            self.socket.sendto(str(Helper(''.encode(), 1, ack_num)).encode(),addr)                          # 发送ACK，防止发送窗口无法右移
                        else:
                            print('server:丢弃数据，序号为:',ack_num)                                                         # 超过窗口，丢弃
            else:                                                                                                           # 未监听到数据
                for index, item in enumerate(fd_timer):
                    if self.send_window[index].is_send != 2:
                        fd_timer[index] = item +1
                data_timer += 1

    def start(self):
        buf = []
        with open('ssend.txt', 'rb') as f:   # 打开发送文本
            while True:                     # 将文本读入buf中
                seq = f.read(500)           # buf中每个字符串为500长度（除了最后一个）
                if len(seq) > 0:
                    buf.append(seq)
                else:
                    break

        while True:
            read_fd, write_fd, error_fd = select.select([self.socket, ], [], [], 1)
            if len(read_fd) > 0:
                msg, addr = self.socket.recvfrom(1024)
                if msg.decode() == 'SR-TEST':
                    self.send(buf)


if __name__ == '__main__':
    server = SRServer()
    server.start()
