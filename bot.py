# Tento skript je bot pro hru, kde stavíte věž z kostek.
# Bot dynamicky měří rychlost pohybující se kostky a na základě toho
# přesně předvídá, kdy stisknout mezerník pro umístění kostky.

# --- Potřebné knihovny ---
# Ujistěte se, že máte nainstalované všechny potřebné knihovny.
# Otevřete terminál (příkazový řádek) a spusťte:
# pip install numpy opencv-python pyautogui keyboard mss

import time
import keyboard
import numpy as np
import cv2
import mss
import pyautogui

# ==============================================================================
# --- NASTAVENÍ BOTA ---
# Tuto část musíte upravit podle vaší hry a obrazovky.
# ==============================================================================

# 1. OBLAST HRY (GAME_REGION)
#    Toto je nejdůležitější nastavení. Musíte botovi říct, kde na obrazovce
#    se hra nachází. Je to obdélník definovaný:
#    - 'left': počet pixelů od levého okraje obrazovky
#    - 'top': počet pixelů od horního okraje obrazovky
#    - 'width': šířka herní oblasti v pixelech
#    - 'height': výška herní oblasti v pixelech
#
#    JAK ZJISTIT HODNOTY?
#    Spusťte si Python v terminálu a napište:
#    >>> import pyautogui
#    >>> pyautogui.displayMousePosition()
#    Poté hýbejte myší a terminál vám bude ukazovat její souřadnice (X, Y).
#    - Najeďte myší na LEVÝ HORNÍ roh herní plochy a zapište si X a Y.
#      To jsou vaše hodnoty 'left' a 'top'.
#    - Najeďte myší na PRAVÝ DOLNÍ roh a zapište si X a Y.
#    - 'width' = (pravý dolní X) - (levý horní X)
#    - 'height' = (pravý dolní Y) - (levý horní Y)
#
#    Zadejte úroveň, na které má bot začít (číslo od 1 do 15).
STARTING_LEVEL = 1

def calculate_game_region(level: int) -> dict:
    """
    Vrátí souřadnice herní oblasti na základě zvolené úrovně.
    Používá vyhledávací tabulku s přesnými hodnotami 'top' pro každou úroveň.
    """
    # Vyhledávací tabulka pro 'top' souřadnici na základě dat od uživatele
    LEVEL_TOPS = {
        1: 810, 2: 747, 3: 689, 4: 628, 5: 569, 6: 518,
        7: 791, 8: 729, 9: 669, 10: 611, 11: 552, 12: 491,
        13: 432, 14: 374, 15: 312,
    }

    if level not in LEVEL_TOPS:
        print(f"Chyba: Neplatná úroveň {level}. Zvolte úroveň od 1 do 15.")
        # V případě neplatného vstupu použijeme jako zálohu úroveň 1
        print("Používám výchozí úroveň 1.")
        level = 1

    # Základní hodnoty, které se nemění
    BASE_LEFT = 660
    BASE_WIDTH = 603
    BASE_HEIGHT = 64

    return {
        'left': BASE_LEFT,
        'top': LEVEL_TOPS[level],
        'width': BASE_WIDTH,
        'height': BASE_HEIGHT
    }

# Herní oblast (GAME_REGION) se nyní počítá až uvnitř funkce main(),
# aby se zajistilo, že se použijí správné hodnoty pro zvolenou úroveň.

# 1.1 OKNO PRO LADĚNÍ (DEBUG WINDOW)
#     Pokud nastavíte na True, bot zobrazí okno, ve kterém v reálném čase
#     uvidíte, co snímá, a kde detekoval kostku. Užitečné pro ladění.
SHOW_DEBUG_WINDOW = True


# 2. BARVY KOSTEK
#    Definice barev pro různé úrovně.
YELLOW_BLOCK_COLOR_RGB = (236, 168, 44)  # Pro úrovně 6-15
BLUE_BLOCK_COLOR_RGB = (45, 170, 232)    # Pro úrovně 1-5

# Výběr barvy (BLOCK_COLOR_RGB) se nyní provádí dynamicky uvnitř funkce main().

#    Jak moc se může skutečná barva lišit od zadané.
#    Větší číslo znamená větší toleranci (např. pro různé odstíny).
COLOR_TOLERANCE = 25


# 3. HERNÍ PARAMETRY
#    Počet sloupců, mezi kterými kostka přeskakuje.
NUM_COLUMNS = 10

#    CÍLOVÝ SLOUPEC (TARGET_COLUMN)
#    Do kterého sloupce má bot mířit? Čísluje se od 0.
#    Pokud máte 10 sloupců (0 až 9), sloupec 4 je pátý zleva.
#    Toto je nejdůležitější hodnota pro míření.
TARGET_COLUMN = 8


# 4. NASTAVENÍ PRO DYNAMICKÉ ČASOVÁNÍ
#    Tato nastavení řídí novou logiku, která měří rychlost kostky
#    a podle toho předvídá, kdy stisknout mezerník.
# ==============================================================================

#    SPUŠTĚNÍ AKCE (TRIGGER)
#    Kolik sloupců PŘED cílovým sloupcem má bot začít s výpočtem.
#    Pokud je cíl sloupec 8 a TRIGGER_COLUMN_OFFSET = 2, bot se "aktivuje",
#    když kostka dorazí do sloupce 6 (při pohybu zleva doprava).
#    Větší hodnota dává botovi více času na výpočet, ale vyžaduje
#    stabilnější rychlost kostky.
#    Doporučená hodnota: 1 nebo 2.
TRIGGER_COLUMN_OFFSET = 2


#    DÁVKA VSTUPŮ (INPUT BURST)
#    Abychom měli jistotu, že náš stisk hra zaregistruje, pošleme jich
#    několik ve velmi rychlém sledu. Tím pokryjeme případné malé
#    nepřesnosti v časování nebo zpoždění ve hře.

#    Počet stisků v jedné dávce.
#    Doporučená hodnota: 3 až 5.
INPUT_BURST_COUNT = 3

#    Prodleva mezi jednotlivými stisky v dávce (v milisekundách).
#    Cílem je trefit herní okno pro vstup, které je často velmi krátké.
#    Doporučená hodnota: 5 až 10 ms.
INPUT_BURST_DELAY_MS = 7


# 5. KOMPENZACE LATENCE
#    Každý systém má malé zpoždění mezi tím, co se stane na obrazovce,
#    a tím, kdy to náš skript zjistí. Tato hodnota (v milisekundách)
#    se odečte od naměřeného času, aby byly výpočty přesnější.
#    Dobrá startovní hodnota je 10-20 ms. Laďte podle potřeby.
DETECTION_LATENCY_MS = 15


# ==============================================================================
# --- KÓD BOTA ---
# Od této části byste neměli nic měnit, pokud nevíte, co děláte.
# ==============================================================================

# Hodnoty jako BLOCK_COLOR_BGR a COLUMN_WIDTH se nyní počítají v main().

def find_block_edges(sct_instance, game_region: dict, block_color_bgr: np.ndarray):
    """
    Snímá herní obrazovku, najde skupinu kostek a vrátí souřadnice jejího
    levého a pravého kraje.
    Vrací: (left_x, right_x, debug_frame)
    """
    try:
        img = sct_instance.grab(game_region)
        img_np = np.array(img)
        frame = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
        debug_frame = frame.copy() if SHOW_DEBUG_WINDOW else None

        lower_bound = np.maximum(0, block_color_bgr - COLOR_TOLERANCE)
        upper_bound = np.minimum(255, block_color_bgr + COLOR_TOLERANCE)
        mask = cv2.inRange(frame, lower_bound, upper_bound)

        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, None, debug_frame

        significant_contours = [c for c in contours if cv2.contourArea(c) > 50]
        if not significant_contours:
            return None, None, debug_frame

        # Najdeme jeden velký ohraničující obdélník pro všechny nalezené kostky
        all_points = np.vstack([c for c in significant_contours])
        x, y, w, h = cv2.boundingRect(all_points)

        left_x = x
        right_x = x + w
        center_y = y + h // 2

        if SHOW_DEBUG_WINDOW:
            # Vykreslíme všechny kontury zeleně a obdélník modře
            cv2.drawContours(debug_frame, significant_contours, -1, (0, 255, 0), 2)
            cv2.rectangle(debug_frame, (x, y), (right_x, y + h), (255, 0, 0), 2)
            # Vykreslíme levý (červený) a pravý (modrý) sledovací bod
            cv2.circle(debug_frame, (left_x, center_y), 5, (0, 0, 255), -1)
            cv2.circle(debug_frame, (right_x, center_y), 5, (255, 0, 0), -1)
            # Vykreslíme dělící čáry mezi sloupci
            for i in range(1, NUM_COLUMNS):
                line_x = int(i * (game_region['width'] / NUM_COLUMNS))
                cv2.line(debug_frame, (line_x, 0), (line_x, game_region['height']), (255, 255, 0), 1)

        return left_x, right_x, debug_frame

    except Exception as e:
        print(f"Vyskytla se chyba při zpracování obrazu: {e}")
        return None, None, None

def main():
    """
    Hlavní smyčka bota s dynamickým měřením rychlosti a prediktivním časováním.
    """
    # --- Lokální proměnné pro správu hry ---
    current_level = STARTING_LEVEL

    # Prvotní nastavení herních parametrů
    if 1 <= current_level <= 5:
        block_color_rgb = BLUE_BLOCK_COLOR_RGB
    else:
        block_color_rgb = YELLOW_BLOCK_COLOR_RGB

    game_region = calculate_game_region(current_level)
    block_color_bgr = np.array(block_color_rgb[::-1])
    column_width = game_region['width'] / NUM_COLUMNS

    print("="*50)
    print(f"Start na úrovni: {current_level}, Cílová oblast: {game_region}")
    print("Bot s dynamickým časováním se spouští za 3 sekundy...")
    print("PŘEPNĚTE SE DO OKNA SE HROU!")
    print("Pro ukončení bota stiskněte a držte klávesu 'q'.")
    print("="*50)
    time.sleep(3)

    # --- Stavové proměnné bota ---
    state = 'AWAITING_CYCLE'
    last_left_column = -1
    direction = 1
    dwell_time_s = None
    column_timestamps = {}

    with mss.mss() as sct:
        while not keyboard.is_pressed('q'):
            left_x, right_x, debug_frame = find_block_edges(sct, game_region, block_color_bgr)

            if SHOW_DEBUG_WINDOW and debug_frame is not None:
                window_title = f"Debug Window (Lvl: {current_level}, Top: {game_region['top']})"
                cv2.imshow(window_title, debug_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            if left_x is None:
                continue

            current_left_column = int(left_x / column_width)

            # --- Logika stavového automatu ---

            # Detekce změny sloupce pro LEVÝ kraj
            if current_left_column != last_left_column:
                detection_time = time.perf_counter()
                inferred_detection_time = detection_time - (DETECTION_LATENCY_MS / 1000.0)

                # Aktualizace směru pohybu
                if last_left_column != -1:
                    new_direction = 1 if current_left_column > last_left_column else -1
                    if new_direction != direction:
                        print(f"Změna směru: {'doprava' if new_direction == 1 else 'doleva'}")
                        direction = new_direction

                print(f"Stav: {state}, Levý sloupec: {current_left_column}, Směr: {'doprava' if direction == 1 else 'doleva'}")

                # STAV: ČEKÁNÍ NA SYNCHRONIZACI (levý kraj na sloupci 0 a pohyb doprava)
                if state == 'AWAITING_CYCLE':
                    if current_left_column == 0 and direction == 1:
                        print("Synchronizace na sloupci 0. Zahajuji měření rychlosti.")
                        state = 'MEASURING'
                        column_timestamps = {current_left_column: inferred_detection_time}

                # STAV: MĚŘENÍ RYCHLOSTI (na základě levého kraje)
                elif state == 'MEASURING':
                    column_timestamps[current_left_column] = inferred_detection_time
                    if len(column_timestamps) > 3:
                        sorted_cols = sorted(column_timestamps.keys())
                        time_diffs = [column_timestamps[sorted_cols[i]] - column_timestamps[sorted_cols[i-1]] for i in range(1, len(sorted_cols))]
                        stable_diffs = [d for d in time_diffs if d > 0.01]
                        if stable_diffs:
                            dwell_time_s = np.mean(stable_diffs)
                            print(f"Změřena rychlost: {dwell_time_s * 1000:.2f} ms na sloupec.")
                            print("Bot je nyní aktivován a připraven k akci (ARMED).")
                            state = 'ARMED'

                last_left_column = current_left_column

            # STAV: PŘIPRAVEN K AKCI (sleduje PRAVÝ kraj)
            if state == 'ARMED' and direction == 1:
                current_right_column = int(right_x / column_width)
                trigger_column = TARGET_COLUMN - TRIGGER_COLUMN_OFFSET

                # Sledujeme, kdy pravý kraj vstoupí do spouštěcího sloupce
                if current_right_column == trigger_column:
                    # --- VÝPOČET A PROVEDENÍ AKCE ---

                    # Cílová pozice v pixelech (střed cílového sloupce)
                    target_pixel = (TARGET_COLUMN * column_width) + 30
                    pixels_to_go = target_pixel - right_x

                    # Rychlost v pixelech za sekundu
                    pixels_per_sec = column_width / dwell_time_s
                    time_to_target_s = pixels_to_go / pixels_per_sec

                    # Predikovaný čas dopadu (od teď)
                    predicted_arrival_time = time.perf_counter() + time_to_target_s

                    print(f"Pravý kraj v trigger sloupci {current_right_column}. Cíl: {TARGET_COLUMN}")
                    print(f"Predikovaný čas dopadu za: {time_to_target_s * 1000:.1f} ms")

                    # Přesné čekání
                    while time.perf_counter() < predicted_arrival_time:
                        pass

                    # Dávka vstupů
                    print(f"==> MEZERNÍK! (Dávka {INPUT_BURST_COUNT} stisků)")
                    for i in range(INPUT_BURST_COUNT):
                        pyautogui.press('space')
                        time.sleep(INPUT_BURST_DELAY_MS / 1000.0)

                    # --- ZVÝŠENÍ ÚROVNĚ A AKTUALIZACE PARAMETRŮ ---
                    current_level += 1
                    print("-" * 20)
                    print(f"Akce provedena. Postup na úroveň {current_level}.")

                    if 1 <= current_level <= 5:
                        block_color_rgb = BLUE_BLOCK_COLOR_RGB
                    else:
                        block_color_rgb = YELLOW_BLOCK_COLOR_RGB

                    game_region = calculate_game_region(current_level)
                    block_color_bgr = np.array(block_color_rgb[::-1])
                    column_width = game_region['width'] / NUM_COLUMNS
                    print(f"Nové parametry: Oblast={game_region}")

                    # Reset stavu a cooldown
                    state = 'AWAITING_CYCLE'
                    dwell_time_s = None
                    column_timestamps = {}
                    print("Aplikuji 3s cooldown...")
                    time.sleep(3)

        print("\nKlávesa 'q' stisknuta, bot se ukončuje.")
        if SHOW_DEBUG_WINDOW:
            cv2.destroyAllWindows()

if __name__ == "__main__":
    print("Vítejte v botovi pro skládání věže!")
    print("Před spuštěním prosím nastavte hodnoty v sekci 'NASTAVENÍ BOTA'.")
    print("\nPotřebné knihovny: pip install numpy opencv-python pyautogui keyboard mss")

    # Zeptáme se uživatele, zda chce spustit bota
    run_bot = input("Chcete spustit bota nyní? (ano/ne): ")
    if run_bot.lower() in ['a', 'ano', 'y', 'yes']:
        main()
    else:
        print("Bot nebyl spuštěn. Upravte nastavení a zkuste to znovu.")