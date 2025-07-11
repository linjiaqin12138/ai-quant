import pytest
import socket
import threading
import json
from lib.adapter.llm import BaiChuan
from lib.modules.agent import Agent


def mock_server(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))
        s.listen(1)
        conn, addr = s.accept()
        with conn:
            data = b""
            while True:
                chunk = conn.recv(1024)
                data += chunk
                if b"\r\n\r\n" in data:
                    break

            print(data)
            headers, body = data.split(b"\r\n\r\n", 1)
            # 检查headers
            expected_headers = {
                b"Content-Type": b"application/json",
                b"Authorization": b"Bearer fake_token",
            }
            print(f"收到的Header: {data}")
            for key, value in expected_headers.items():
                assert key in headers, f"缺少预期的header: {key.decode('utf-8')}"
                assert value in headers, f"header {key.decode('utf-8')} 的值不正确"

            content_length = int(
                [
                    line.split(b":")[1].strip()
                    for line in headers.split(b"\r\n")
                    if b"Content-Length" in line
                ][0]
            )
            while len(body) < content_length:
                body += conn.recv(1024)

            print(f"收到的数据: {body}")

            expected_data = {
                "model": "Baichuan3-Turbo-128k",
                "messages": [{"role": "user", "content": "你好"}],
                "stream": False,
            }
            assert json.loads(body.decode("utf-8")) == expected_data

            response_body = json.dumps(
                {
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "created": 1234567890,
                    "model": "Baichuan3-Turbo-128k",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "你好!我是百川AI助手,很高兴为您服务。",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 2,
                        "completion_tokens": 18,
                        "total_tokens": 20,
                    },
                }
            )

            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                f"\r\n"
                f"{response_body}"
            )
            conn.sendall(response.encode("utf-8"))


@pytest.fixture
def mock_baichuan_server():
    port = 12345
    server_thread = threading.Thread(target=mock_server, args=(port,))
    server_thread.start()
    yield port
    server_thread.join(timeout=1)


def test_baichuan_agent(mock_baichuan_server):

    agent = Agent(
        BaiChuan(
            endpoint=f"http://127.0.0.1:{mock_baichuan_server}", api_key="fake_token"
        )
    )

    response = agent.ask("你好")

    assert response == "你好!我是百川AI助手,很高兴为您服务。"
