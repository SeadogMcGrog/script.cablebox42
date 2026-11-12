"""Switch-time reference: three test spots queued in a plain Kodi video playlist
(no CableBox involved; turn the TV off first). Run inside the rig with notes.py."""
import json, socket
s = socket.create_connection(("127.0.0.1", 9090))


def rpc(m, p):
    s.sendall(json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode())


rpc("Playlist.Clear", {"playlistid": 1})
for f in ("Ad 2.mp4", "Ad 4.mp4", "Ad 6.mp4"):
    rpc("Playlist.Add", {"playlistid": 1, "item": {"file": "/root/library/ads/" + f}})
rpc("Player.Open", {"item": {"playlistid": 1, "position": 0}})
