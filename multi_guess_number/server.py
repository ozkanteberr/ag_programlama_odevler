"""Dort basamakli sayi tahmin oyununun TCP sunucusu."""

import json
import random
import socket
import threading
from typing import Dict, Optional


HOST = "0.0.0.0"
PORT = 5000
PLAYERS = ("client1", "client2", "client3")
MAX_GUESSES = 10
STARTING_POINTS = 1000
GUESS_COST = 50
CORRECT_PLACE_POINTS = 25
WRONG_PLACE_POINTS = 10
WIN_BONUS = 500
REMAINING_GUESS_BONUS = 25


def create_secret() -> str:
    """Ilk basamagi sifir olmayan, rakamlari farkli bir sayi uretir."""
    first = random.choice("123456789")
    remaining_digits = [digit for digit in "0123456789" if digit != first]
    return first + "".join(random.sample(remaining_digits, 3))


def validate_guess(guess: object) -> Optional[str]:
    if not isinstance(guess, str) or len(guess) != 4 or not guess.isdigit():
        return "Tahmin tam olarak 4 rakamdan olusmalidir."
    if guess[0] == "0":
        return "Tahmin 0 ile baslayamaz."
    if len(set(guess)) != 4:
        return "Tahmindeki rakamlar birbirinden farkli olmalidir."
    return None


def score_guess(secret: str, guess: str) -> tuple[int, int]:
    correct_place = sum(a == b for a, b in zip(secret, guess))
    wrong_place = sum(digit in secret for digit in guess) - correct_place
    return correct_place, wrong_place


class GameServer:
    def __init__(self) -> None:
        self.secret = create_secret()
        self.clients: Dict[str, socket.socket] = {}
        self.remaining = {player: MAX_GUESSES for player in PLAYERS}
        self.points = {player: STARTING_POINTS for player in PLAYERS}
        self.previous_guesses = {player: set() for player in PLAYERS}
        self.turn_index = 0
        self.started = False
        self.finished = False
        self.lock = threading.RLock()

    @staticmethod
    def send(sock: socket.socket, message: dict) -> None:
        sock.sendall((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))

    def broadcast(self, message: dict) -> None:
        broken = []
        for player, sock in list(self.clients.items()):
            try:
                self.send(sock, message)
            except OSError:
                broken.append(player)
        for player in broken:
            self.clients.pop(player, None)

    def send_turn(self) -> None:
        player = PLAYERS[self.turn_index]
        self.broadcast({"type": "turn", "player": player})
        print(f"Sira: {player}")

    def join(self, player: object, sock: socket.socket) -> bool:
        with self.lock:
            if self.started or self.finished:
                self.send(sock, {"type": "error", "message": "Oyun zaten basladi."})
                return False
            if player not in PLAYERS:
                self.send(sock, {"type": "error", "message": "Gecersiz oyuncu adi."})
                return False
            if player in self.clients:
                self.send(sock, {"type": "error", "message": f"{player} zaten bagli."})
                return False

            self.clients[player] = sock
            self.send(
                sock,
                {
                    "type": "welcome",
                    "player": player,
                    "remaining": self.remaining[player],
                    "points": self.points[player],
                },
            )
            self.broadcast(
                {
                    "type": "info",
                    "message": f"{player} baglandi ({len(self.clients)}/3).",
                }
            )
            print(f"{player} baglandi.")

            if len(self.clients) == len(PLAYERS):
                self.started = True
                self.broadcast(
                    {
                        "type": "info",
                        "message": "Tum oyuncular baglandi. Oyun basliyor!",
                    }
                )
                self.send_turn()
            return True

    def handle_guess(self, player: str, guess: object) -> None:
        with self.lock:
            sock = self.clients.get(player)
            if sock is None:
                return
            if self.finished:
                self.send(sock, {"type": "error", "message": "Oyun sona erdi."})
                return
            if not self.started:
                self.send(sock, {"type": "error", "message": "Diger oyuncular bekleniyor."})
                return
            current_player = PLAYERS[self.turn_index]
            if player != current_player:
                self.send(
                    sock,
                    {"type": "error", "message": f"Simdi {current_player} oynuyor."},
                )
                return

            error = validate_guess(guess)
            if error:
                self.send(sock, {"type": "error", "message": error, "retry": True})
                return

            assert isinstance(guess, str)
            if guess in self.previous_guesses[player]:
                self.send(
                    sock,
                    {
                        "type": "error",
                        "message": "Ayni tahmini daha once yaptiniz. Baska bir sayi deneyin.",
                        "retry": True,
                    },
                )
                return

            self.previous_guesses[player].add(guess)
            self.remaining[player] -= 1
            correct, misplaced = score_guess(self.secret, guess)
            result = f"+{correct} -{misplaced}"
            point_change = (
                -GUESS_COST
                + correct * CORRECT_PLACE_POINTS
                + misplaced * WRONG_PLACE_POINTS
            )
            if correct == 4:
                point_change += WIN_BONUS + self.remaining[player] * REMAINING_GUESS_BONUS
            self.points[player] += point_change
            print(
                f"{player} tahmini: {guess} | Sonuc: {result} | "
                f"Puan degisimi: {point_change:+d} | Toplam: {self.points[player]} | "
                f"Kalan hak: {self.remaining[player]}"
            )

            # Her istemciye ayri mesaj gider; tahmini yalnizca tahmini yapan gorur.
            for recipient, client_sock in list(self.clients.items()):
                shown_guess = guess if recipient == player else "****"
                try:
                    self.send(
                        client_sock,
                        {
                            "type": "result",
                            "player": player,
                            "guess": shown_guess,
                            "score": result,
                            "point_change": point_change,
                            "points": self.points.copy(),
                            "remaining": self.remaining[player],
                        },
                    )
                except OSError:
                    pass

            if correct == 4:
                self.finished = True
                self.broadcast(
                    {
                        "type": "game_over",
                        "winner": player,
                        "secret": self.secret,
                        "message": f"{player} sayiyi bildi!",
                        "points": self.points.copy(),
                    }
                )
                print(f"Oyun bitti. Kazanan: {player}, sayi: {self.secret}")
                return

            if all(value == 0 for value in self.remaining.values()):
                self.finished = True
                self.broadcast(
                    {
                        "type": "game_over",
                        "winner": None,
                        "secret": self.secret,
                        "message": "Tum tahmin haklari bitti.",
                        "points": self.points.copy(),
                    }
                )
                print(f"Oyun bitti. Sayiyi bilen olmadi. Sayi: {self.secret}")
                return

            # Hakki biten oyuncular varsa onlar atlanir.
            for _ in PLAYERS:
                self.turn_index = (self.turn_index + 1) % len(PLAYERS)
                if self.remaining[PLAYERS[self.turn_index]] > 0:
                    break
            self.send_turn()

    def disconnect(self, player: str, sock: socket.socket) -> None:
        with self.lock:
            if self.clients.get(player) is not sock:
                return
            self.clients.pop(player, None)
            print(f"{player} baglantiyi kesti.")
            if self.started and not self.finished:
                self.finished = True
                self.broadcast(
                    {
                        "type": "game_over",
                        "winner": None,
                        "secret": self.secret,
                        "message": f"{player} ayrildigi icin oyun sona erdi.",
                        "points": self.points.copy(),
                    }
                )

    def client_worker(self, sock: socket.socket, address: tuple[str, int]) -> None:
        player = ""
        file = sock.makefile("r", encoding="utf-8")
        try:
            first_line = file.readline()
            if not first_line:
                return
            try:
                hello = json.loads(first_line)
            except json.JSONDecodeError:
                self.send(sock, {"type": "error", "message": "Gecersiz baglanti mesaji."})
                return
            if hello.get("type") != "join":
                self.send(sock, {"type": "error", "message": "Once oyuna katilmalisiniz."})
                return
            player = hello.get("player", "")
            if not self.join(player, sock):
                return

            for line in file:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    self.send(sock, {"type": "error", "message": "Gecersiz mesaj."})
                    continue
                if message.get("type") == "guess":
                    self.handle_guess(player, message.get("guess"))
        except (ConnectionError, OSError):
            pass
        finally:
            file.close()
            if player:
                self.disconnect(player, sock)
            try:
                sock.close()
            except OSError:
                pass
            print(f"Baglanti kapandi: {address[0]}:{address[1]}")

    def run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((HOST, PORT))
            server_socket.listen()
            server_socket.settimeout(0.5)
            print(f"Sunucu {HOST}:{PORT} adresinde dinliyor.")
            print(f"(Ogretmen testi icin gizli sayi: {self.secret})")
            try:
                while not self.finished:
                    try:
                        sock, address = server_socket.accept()
                    except socket.timeout:
                        continue
                    threading.Thread(
                        target=self.client_worker,
                        args=(sock, address),
                        daemon=True,
                    ).start()
            except KeyboardInterrupt:
                print("\nSunucu kapatiliyor...")


if __name__ == "__main__":
    GameServer().run()
