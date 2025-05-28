import tkinter as tk
import tkinter.messagebox as messagebox
from PIL import Image, ImageTk
import chess
import chess.engine
import os
from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")
print(api_key)
openai = OpenAI(api_key=api_key)

BOARD_SIZE = 8
SQUARE_SIZE = 64  # 픽셀
images = {}

# Stockfish 경로
ENGINE_PATH = "stockfish/stockfish-windows-x86-64-avx2"

# 기물 심볼 → 파일 이름 매핑
piece_image_map = {
    'P': 'wp.PNG', 'R': 'wr.PNG', 'N': 'wn.PNG', 'B': 'wb.PNG', 'Q': 'wq.PNG', 'K': 'wk.PNG',
    'p': 'bp.PNG', 'r': 'br.PNG', 'n': 'bn.PNG', 'b': 'bb.PNG', 'q': 'bq.PNG', 'k': 'bk.PNG'
}

def choose_player_color():
    selection = {"color": None}

    def set_white():
        selection["color"] = chess.WHITE
        color_window.destroy()

    def set_black():
        selection["color"] = chess.BLACK
        color_window.destroy()

    color_window = tk.Tk()
    color_window.title("색상 선택")

    label = tk.Label(color_window, text="플레이할 색상을 선택하세요!", font=("Arial", 14))
    label.pack(pady=10)

    white_btn = tk.Button(color_window, text="⚪ 화이트", width=20, command=set_white)
    white_btn.pack(pady=5)

    black_btn = tk.Button(color_window, text="⚫ 블랙", width=20, command=set_black)
    black_btn.pack(pady=5)

    color_window.mainloop()
    return selection["color"]


class ChessApp:
    def __init__(self, root, player_color):
        self.root = root
        self.board = chess.Board()
        self.player_color = player_color
        self.selected_square = None

        # 체스판 캔버스 (왼쪽)
        self.canvas = tk.Canvas(root, width=BOARD_SIZE * SQUARE_SIZE, height=BOARD_SIZE * SQUARE_SIZE)
        self.canvas.pack(side=tk.LEFT)

        # 사이드 패널 (오른쪽)
        self.side_panel = tk.Frame(root, width=200)
        self.side_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        # 버튼들
        self.hunsu_button = tk.Button(self.side_panel, text="훈수 요청하기", command=self.ask_gpt_about_move, width=20, height=2)
        self.hunsu_button.pack(pady=20)

        self.undo_button = tk.Button(self.side_panel, text="뒤로 돌리기", command=self.undo_move, width=20, height=2)
        self.undo_button.pack(pady=20)

        self.engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)

        self.load_images()
        self.draw_board()

        self.canvas.bind("<Button-1>", self.on_click)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_images(self):
        for symbol, filename in piece_image_map.items():
            path = f"pieces/{filename}"
            if os.path.exists(path):
                img = Image.open(path).resize((SQUARE_SIZE, SQUARE_SIZE))
                images[symbol] = ImageTk.PhotoImage(img)
            else:
                print(f"❌ 이미지 없음: {path}")

    def draw_board(self):
        self.canvas.delete("all")
        light = "#F0D9B5"
        dark = "#B58863"

        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                display_row = row if self.player_color == chess.WHITE else 7 - row
                display_col = col if self.player_color == chess.WHITE else 7 - col

                x1 = display_col * SQUARE_SIZE
                y1 = display_row * SQUARE_SIZE
                x2 = x1 + SQUARE_SIZE
                y2 = y1 + SQUARE_SIZE

                fill = light if (row + col) % 2 == 0 else dark
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=fill)

        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                row = 7 - (square // 8)
                col = square % 8

                display_row = row if self.player_color == chess.WHITE else 7 - row
                display_col = col if self.player_color == chess.WHITE else 7 - col

                symbol = piece.symbol()
                if symbol in images:
                    self.canvas.create_image(display_col * SQUARE_SIZE, display_row * SQUARE_SIZE,
                                             image=images[symbol], anchor="nw")

    def on_click(self, event):
        col = event.x // SQUARE_SIZE
        row = event.y // SQUARE_SIZE

        board_row = 7 - row if self.player_color == chess.WHITE else row
        board_col = col if self.player_color == chess.WHITE else 7 - col

        square = chess.square(board_col, board_row)

        if self.selected_square is None:
            if self.board.piece_at(square):
                self.selected_square = square
        else:
            move = chess.Move(self.selected_square, square)
            if (
                    self.board.piece_at(self.selected_square)
                    and self.board.piece_at(self.selected_square).piece_type == chess.PAWN
                    and (
                    (self.player_color == chess.WHITE and chess.square_rank(square) == 7) or
                    (self.player_color == chess.BLACK and chess.square_rank(square) == 0) )
            ):
                move = chess.Move(self.selected_square, square, promotion=chess.QUEEN)

            if move in self.board.legal_moves:
                self.board.push(move)
                self.draw_board()
                self.analyse_position()
            self.selected_square = None

    def analyse_position(self):
        if self.board.is_checkmate():
            print("♟️ 체크메이트! 게임이 종료되었습니다.")
            messagebox.showinfo("게임 종료", "체크메이트! 게임이 끝났습니다.")
            return
        elif self.board.is_stalemate():
            print("🔒 스테일메이트! 무승부입니다.")
            messagebox.showinfo("게임 종료", "스테일메이트! 무승부입니다.")
            return
        elif self.board.is_insufficient_material():
            print("📭 말이 부족해 무승부입니다.")
            messagebox.showinfo("게임 종료", "말 부족으로 무승부입니다.")
            return

        if len(self.board.move_stack) >= 1:
            last_move = self.board.peek()

            # 수 돌리기 전 상태 복구
            self.board.pop()
            info_before = self.engine.analyse(self.board, chess.engine.Limit(time=0.1))
            self.board.push(last_move)  # 복구

            info_after = self.engine.analyse(self.board, chess.engine.Limit(time=0.1))

            score_before = info_before["score"].pov(self.player_color).score()
            score_after = info_after["score"].pov(self.player_color).score()

            if score_before is not None and score_after is not None:
                delta = score_after - score_before
                print(f"📊 내 기준 평가 변화: {score_before} → {score_after} (Δ {delta})")
                if delta < -200:
                    print("🚨 블런더입니다! 내 입장에서 큰 손해입니다.")
        else:
            print("🔍 아직 이전 수가 없어서 블런더 감지를 생략합니다.")


    def ask_gpt_about_move(self, fen, move_uci):
        prompt = f"""
체스 포지션 (FEN): {fen}
마지막 수: {move_uci}

이 수는 전략적으로 어떤 의미가 있는가요? 좋은 수인가요? 장단점을 설명해주세요.
"""
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "넌 체스 코치로서 전략과 수의 의도를 설명해줘야 해."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return response['choices'][0]['message']['content']

    # ✅ 한 수 되돌리기

    def undo_move(self):
        if self.board.move_stack:
            self.board.pop()
            self.draw_board()
            print("↩️ 한 수 되돌림 완료")
        else:
            print("⚠️ 되돌릴 수 있는 수가 없습니다.")

    def on_close(self):
        self.engine.quit()
        self.root.destroy()


# 색상 선택
player_color = choose_player_color()

# 메인 창 시작
root = tk.Tk()
root.title("체스 앱 (사이드 버튼 추가)")
app = ChessApp(root, player_color)
root.mainloop()