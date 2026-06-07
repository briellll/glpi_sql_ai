"""
Utilitarios de estilizacao de terminal com cores ANSI.
Design com tags coloridas, boxes e separadores.
"""

import shutil
import sys

# ---------------------------------------------------------------------------
# Ativa processamento ANSI no Windows (Virtual Terminal)
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    import ctypes as _ctypes

    _STD_OUTPUT_HANDLE = -11
    _ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

    try:
        _kernel32 = _ctypes.windll.kernel32
        _handle = _kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
        _mode = _ctypes.c_uint32()
        _kernel32.GetConsoleMode(_handle, _ctypes.byref(_mode))
        _kernel32.SetConsoleMode(
            _handle, _mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
        )
    except Exception:
        pass

    # Forca stdout para UTF-8 onde possivel
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Constantes de cor
# ---------------------------------------------------------------------------
R = "\033[0m"
B = "\033[1m"
D = "\033[2m"

C_WHITE = "\033[37m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"

# Laranja — fallback para amarelo em terminais sem 256 cores
C_ORANGE = "\033[38;5;214m"

# Tons mais escuros para detalhes
C_DM = "\033[90m"   # grey

# ==========================================================================
#  Funcoes publicas
# ==========================================================================

def _term_width() -> int:
    return shutil.get_terminal_size().columns


def banner(title: str, subtitle: str = "", width: int | None = None) -> None:
    """Cabecalho com borda dupla estilo box."""
    if width is None:
        width = min(_term_width(), 80)
    top = f"{D}{C_ORANGE}╔{'═' * (width - 2)}╗{R}"
    mid_fmt = f"{D}{C_ORANGE}║{R}"
    bot = f"{D}{C_ORANGE}╚{'═' * (width - 2)}╝{R}"

    print(top)
    _centered(title, width, B + C_ORANGE, mid_fmt)
    if subtitle:
        _centered(subtitle, width, C_ORANGE, mid_fmt)
    print(bot)
    print()


def _centered(text: str, width: int, color: str, edge: str) -> None:
    visible = text
    padding = max(0, (width - 2) - len(visible)) // 2
    left = " " * padding
    right = " " * ((width - 2) - len(visible) - padding)
    print(f"{edge}{left}{color}{visible}{R}{right}{edge}")


def prompt_str(prompt_text: str = "Voce") -> str:
    """Retorna prefixo colorido para o prompt."""
    return f"\n{B}{C_ORANGE}▸{R} {B}{prompt_text}{R} "


def status(tag: str, msg: str, tag_color: str = C_CYAN, width: int | None = None) -> None:
    """Linha de status:  [SQL]  Gerando consulta..."""
    if width is None:
        width = min(_term_width(), 80)
    lhs = f"  [{tag}]"
    target = 16  # largura fixa para alinhar mensagens
    padded = lhs.ljust(target)
    print(f"{D}{tag_color}{padded}{R} {msg}")


def display(text: str, title: str = "", color: str = "") -> None:
    """Exibe texto com titulo colorido opcional, sem bordas."""
    print()
    if title:
        print(f"  {B}{color}{title}{R}")
        divider()
    for line in text.strip().split("\n"):
        print(f"  {line}")
    print()


def ok(text: str = "") -> None:
    print(f"  {B}{C_GREEN}OK{R} {text}")


def fail(text: str = "") -> None:
    print(f"  {B}{C_RED}ERR{R} {text}")


def warn(text: str = "") -> None:
    print(f"  {B}{C_YELLOW}!!{R} {text}")


def divider(char: str = "─", color: str = D, width: int | None = None) -> None:
    if width is None:
        width = min(_term_width(), 80)
    print(f"{color}{char * width}{R}")
