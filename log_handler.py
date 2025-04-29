from enum import Enum
import socket
import time

from configs import *

class DataType(Enum):
    FROM_CLIENT = 0
    FROM_SERVER = 1

class ConversationType(Enum):
    HEADER = 0
    DATA = 1

class Conversation:
    def __init__(self, conversation_type: ConversationType, data: bytes, data_type: DataType):
        self.conversation_type = conversation_type
        if conversation_type == ConversationType.HEADER:
            self.data = data
        self.data_type = data_type
        self.length = len(data)
        self.time = time.time()

class _Tracker:
    def __init__(self, id: int, url: str):
        self.id = id
        self.url = url
        self.init_time = time.time()
        self.conversation_history = []
        self.client_buffer = b""
        self.server_buffer = b""
        self.client_data_flag = False
        self.server_data_flag = False

    def get_size(self):
        """
        Get the total size of all data exchanged in this request.
        """
        size = 0
        for conversation in self.conversation_history:
            size += conversation.length
        return size

    def on_data(self, data: bytes, data_type: DataType):
        """
        Process incoming data chunks.
        Headers are buffered to ensure they are stored in a single conversation.
        Data is processed directly without buffering.
        """
        # Get the appropriate buffer and flag
        buffer = self.client_buffer if data_type == DataType.FROM_CLIENT else self.server_buffer
        data_flag = self.client_data_flag if data_type == DataType.FROM_CLIENT else self.server_data_flag
        
        # HTTP method markers for detecting new requests
        start_markers = [b"GET ", b"POST ", b"PUT ", b"DELETE ", b"HEAD ", 
                        b"OPTIONS ", b"TRACE ", b"CONNECT ", b"PATCH ", b"HTTP/"]
        
        if not data_flag:  # Processing headers
            buffer += data
            
            # Check for complete header
            header_end = buffer.find(b'\r\n\r\n')
            if header_end != -1:
                # Extract complete header
                header_data = buffer[:header_end+4]
                remaining_data = buffer[header_end+4:]
                
                # Store header conversation
                header_conv = Conversation(
                    conversation_type=ConversationType.HEADER,
                    data=header_data,
                    data_type=data_type
                )
                self.conversation_history.append(header_conv)
                
                # Process any remaining data as body
                if len(remaining_data) > 0:
                    data_conv = Conversation(
                        conversation_type=ConversationType.DATA,
                        data=remaining_data,
                        data_type=data_type
                    )
                    self.conversation_history.append(data_conv)
                
                # Clear buffer and update flag
                buffer = b""
                if data_type == DataType.FROM_CLIENT:
                    self.client_data_flag = True
                    self.client_buffer = buffer
                else:
                    self.server_data_flag = True
                    self.server_buffer = buffer
        else:  # Processing data
            # Check for new request in current data
            new_request_pos = -1
            for marker in start_markers:
                pos = data.find(marker)
                if pos != -1 and (new_request_pos == -1 or pos < new_request_pos):
                    new_request_pos = pos
            
            if new_request_pos != -1:
                # Found new request, process data before it
                if new_request_pos > 0:
                    data_conv = Conversation(
                        conversation_type=ConversationType.DATA,
                        data=data[:new_request_pos],
                        data_type=data_type
                    )
                    self.conversation_history.append(data_conv)
                
                # Process the new request header
                remaining_data = data[new_request_pos:]
                if data_type == DataType.FROM_CLIENT:
                    self.client_buffer = remaining_data
                    self.client_data_flag = False
                else:
                    self.server_buffer = remaining_data
                    self.server_data_flag = False
            else:
                # No new request, process entire chunk as data
                data_conv = Conversation(
                    conversation_type=ConversationType.DATA,
                    data=data,
                    data_type=data_type
                )
                self.conversation_history.append(data_conv)

class LoggingSocketDecorator():
    def __init__(self, socket: socket.socket, tracker: _Tracker):
        self._socket = socket
        self._tracker = tracker

    def _wrapper(self, method, method_name):
        def inner(*args, **kwargs):
            if method.__name__ in ["send", "sendall"]:
                data = args[0]
                self._tracker.on_data(data, DataType.FROM_CLIENT)

            result = method(*args, **kwargs)

            if method.__name__ == "recv":
                self._tracker.on_data(result, DataType.FROM_SERVER)

            return result
        return inner

    def __getattr__(self, attr):
        method = getattr(self._socket, attr)

        if callable(method):
            return self._wrapper(method, attr)

        return method

class RequestTracker:
    def __init__(self):
        self.request_list = []
        self._count = 0

    def init_request(self, url: str):
        tracker = _Tracker(self._count, url)
        self._count += 1
        self.request_list.append(tracker)
        return tracker

    def dump(self, file_path: str, sort_lambda=lambda x: x.init_time):
        req_list = sorted(self.request_list, key=sort_lambda)
        with open(file_path, 'w') as f:
            for tracker in req_list:
                f.write(f"Request {tracker.id} - {tracker.url} - {tracker.init_time} - {tracker.get_size() / 1024 / 1024:.2f} MB\n")
                for conversation in tracker.conversation_history:
                    f.write(f"{conversation.data_type.name} - {conversation.conversation_type.name} - {conversation.length} - {conversation.time}\n")
                    f.write(HISTORY_DIVIDER_H2 + "\n")
                    if conversation.conversation_type == ConversationType.HEADER:
                        f.write(f"{conversation.data.decode()}")
                f.write(HISTORY_DIVIDER_H1 + "\n")


request_tracker = RequestTracker()