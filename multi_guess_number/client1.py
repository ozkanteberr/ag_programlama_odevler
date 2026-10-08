"""Sayi tahmin oyunu - birinci oyuncu istemcisi."""

import json
import socket
import threading

PLAYER_NAME = "client1"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000


def send(sock: socket.socket, message: dict) -> None:
    sock.sendall((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))


def receive_messages(sock: socket.socket, my_turn: threading.Event, done: threading.Event) -> None:
    try:
        with sock.makefile("r", encoding="utf-8") as stream:
            for line in stream:
                message = json.loads(line)
                kind = message.get("type")
                if kind == "welcome":
                    print(
                        f"{message['player']} olarak baglandiniz. "
                        f"Hakkiniz: {message['remaining']} | Puaniniz: {message['points']}"
                    )
                elif kind == "info":
                    print(f"[BILGI] {message['message']}")
                elif kind == "result":
                    print(
                        f"[SONUC] {message['player']} -> {message['guess']} | "
                        f"{message['score']} | Puan degisimi: {message['point_change']:+d} | "
                        f"Kalan hak: {message['remaining']}"
                    )
                    ranking = sorted(message["points"].items(), key=lambda item: (-item[1], item[0]))
                    print("[PUAN TABLOSU] " + " | ".join(f"{p}: {s}" for p, s in ranking))
                elif kind == "turn":
                    if message["player"] == PLAYER_NAME:
                        print("\nSira sizde.")
                        my_turn.set()
                    else:
                        print(f"Sira {message['player']} oyuncusunda.")
                elif kind == "error":
                    print(f"[HATA] {message['message']}")
                    if message.get("retry"):
                        my_turn.set()
                elif kind == "game_over":
                    print(f"\n[OYUN BITTI] {message['message']} Tutulan sayi: {message['secret']}")
                    ranking = sorted(message["points"].items(), key=lambda item: (-item[1], item[0]))
                    print("[FINAL PUANLARI] " + " | ".join(f"{p}: {s}" for p, s in ranking))
                    done.set()
                    my_turn.set()
                    return
    except (ConnectionError, OSError, json.JSONDecodeError):
        if not done.is_set():
            print("Sunucu baglantisi kesildi.")
    finally:
        done.set()
        my_turn.set()


def main() -> None:
    my_turn = threading.Event()
    done = threading.Event()
    try:
        with socket.create_connection((SERVER_HOST, SERVER_PORT)) as sock:
            send(sock, {"type": "join", "player": PLAYER_NAME})
            threading.Thread(
                target=receive_messages, args=(sock, my_turn, done), daemon=True
            ).start()
            while not done.is_set():
                my_turn.wait()
                if done.is_set():
                    break
                my_turn.clear()
                guess = input("4 basamakli tahmininiz: ").strip()
                send(sock, {"type": "guess", "guess": guess})
    except ConnectionRefusedError:
        print("Sunucuya baglanilamadi. Once server.py dosyasini calistirin.")
    except (ConnectionError, OSError):
        print("Baglanti sona erdi.")
    except KeyboardInterrupt:
        print("\nOyundan ayrildiniz.")


if __name__ == "__main__":
    main()
