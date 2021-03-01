import asyncio
import json
from optparse import OptionParser


def parse_args():
    parser = OptionParser()

    parser.add_option("-i", "--ip", dest="ip", default="9.134.9.104", help="server ip")
    parser.add_option("-p", "--port", dest="port", default="12345", help="server port")
    return parser.parse_args()


class Conn(object):
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.addr = writer.get_extra_info('peername')


class Player(object):
    def __init__(self, ident):
        self.ident = ident
        self.score = 0
        self.x = 0
        self.y = 0
        self.z = 0


class App(object):
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.conns = {}
        self.players = {}

    def add_conn(self, reader, writer):
        cn = Conn(reader, writer)
        self.conns[id(cn)] = cn
        return cn

    def del_conn(self, cn):
        if id(cn) in self.conns:
            del self.conns[id(cn)]
            return True
        return False

    async def boradcast(self, message, drain=True):
        for c in self.conns.values():
            print(f"boradcast to {c.addr}")
            c.writer.write(message)

        if drain:
            for c in self.conns.values():
                await c.writer.drain()

    def on_join(self, proto):
        player_id = proto.get("id")
        if not player_id:
            return

        self.players[player_id] = Player(player_id)

    def on_exit(self, proto):
        player_id = proto.get("id")
        if not player_id:
            return

        if player_id not in self.players:
            return

        self.players.pop(player_id)

    def on_move(self, proto):
        player_id = proto.get("id")
        if not player_id:
            return

        if player_id not in self.players:
            return

        self.players[player_id].x = proto.get("x", 0)
        self.players[player_id].z = proto.get("z", 0)

    def update(self, data):
        proto = json.loads(data.decode("utf-8"))
        typ = proto.get("type")
        if typ == "JOIN":
            self.on_join(proto)
        elif typ == "EXIT":
            self.on_exit(proto)
        elif typ == "MOVE":
            self.on_move(proto)

    async def handler(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print("connection peer: ", addr)
        cn = self.add_conn(reader, writer)

        while True:
            raw_length = await reader.read(4)
            if not raw_length or len(raw_length) < 4:
                break

            content_length = int.from_bytes(raw_length, "big")
            print(f"{addr} send content length: {content_length}")
            await self.boradcast(raw_length, drain=False)

            data = await reader.read(content_length)
            if not data or len(data) < content_length:
                break

            print(f"{addr} send content: {data[0:64]}")
            await self.boradcast(data)

            self.update(data)

        print("disconnect peer: ", addr)
        writer.close()
        self.del_conn(cn)

    def start(self):
        loop = asyncio.get_event_loop()
        coro = asyncio.start_server(self.handler, self.ip, self.port, loop=loop)
        server = loop.run_until_complete(coro)

        print('Serving on {}'.format(server.sockets[0].getsockname()))
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass

        # Close the server
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()


def main():
    (options, _) = parse_args()
    app = App(options.ip, options.port)
    app.start()
    


if __name__ == "__main__":
    main()
