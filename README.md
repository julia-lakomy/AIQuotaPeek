# AIQuotaPeek

AIQuotaPeek to projekt osobistego widżetu **Limity AI** dla panelu KDE Plasma 6. Widżet pokazuje, ile procent limitu **pozostało** na kontach ChatGPT i Claude. Po kliknięciu wyświetla dostępne limity sesji i tygodnia, czasy resetu oraz godzinę ostatniego udanego odczytu.

Przykład napisu w panelu: `GPT 42% · Claude 12%`. Gdy serwis podaje dwa limity, panel pokazuje niższy z dwóch pozostałych procentów. Szczegóły każdego limitu są w rozwijanym widżecie. `—` oznacza, że nie ma jeszcze odczytu dla danej usługi.

## Szybki start

Projekt został przygotowany dla tego komputera z Ubuntu 26.04 i KDE Plasma 6. Instalator zakłada dostępność Falkona pod `/usr/bin/falkon`, Pythona 3, narzędzi Plasma i KWin, `systemctl --user` oraz `rg`. Jeśli brakuje modułów PyQt6 WebEngine, pobiera odpowiednie pakiety przez `apt download` i rozpakowuje je do `.deps` w projekcie. Nie instaluje samego Falkona.

W katalogu projektu uruchom:

```bash
bash scripts/install.sh
```

Instalator dodaje pakiet widżetu, skrypt KWin do wykrywania pełnego ekranu i usługę użytkownika `limity-ai-widget.service`. Nie wymaga hasła administratora. Jeśli widżet nie jest jeszcze w panelu, dodaj go w KDE pod nazwą **Limity AI**.

1. Kliknij widżet, aby otworzyć dedykowanego Falkona ze stronami Usage ChatGPT i Claude.
2. Zaloguj się na obu stronach tak jak zwykle. Haseł i kodów nie wpisuje się do widżetu.
3. Kliknij w widżecie **Zakończ logowanie** albo zamknij wszystkie okna dedykowanego Falkona. Pozwoli to czytnikowi ponownie użyć jego profilu.
4. Poczekaj na pierwszy odczyt. Falkon nie musi być później otwarty.

Okno Falkona otwiera się wyłącznie po działaniu użytkownika w widżecie. Gdy logowanie wygaśnie, kliknięcie widżetu otworzy stronę wymagającą ponownego logowania.

## Codzienne używanie

| Element | Co oznacza |
| --- | --- |
| `GPT 42% · Claude 12%` | Najniższy dostępny procent pozostałego limitu każdej usługi. |
| „Obecna sesja” | Pozostały procent krótkiego limitu, jeśli strona Usage go podaje. |
| „Limit tygodniowy” | Pozostały procent limitu tygodniowego. |
| „Reset” | Lokalny dzień i godzina resetu w strefie `Europe/Warsaw`. Znak `~` oznacza godzinę obliczoną z podanego przez serwis czasu względnego. |
| „Odczyt” | Godzina ostatniego udanego pobrania danych danej usługi. |
| „brak danych” | Tego limitu nie ma na stronie, nie został jeszcze odczytany albo odczyt się nie powiódł. |

Czytnik odświeża strony automatycznie co 5 minut. Przycisk **⟳** w szczegółach zleca ręczny odczyt. Przyciski **ChatGPT ↗** i **Claude ↗** otwierają wybraną stronę w dedykowanym Falkonie, na przykład gdy trzeba ponownie się zalogować.

Podczas aktywnej gry w trybie pełnoekranowym automatyczny odczyt jest wstrzymany. Panel pokazuje ostatnie znane wartości, a szczegóły komunikat „Wstrzymano podczas pełnego ekranu”. Po opuszczeniu pełnego ekranu czytnik wznawia pracę po około 15 sekundach. Widżet nie otwiera wtedy żadnego okna.

Na obecnej stronie Usage tego konta ChatGPT widoczny jest procent limitu tygodniowego, ale nie ma osobnego procentu bieżącej sesji. Dlatego widżet pokazuje przy sesji ChatGPT „brak danych”; nie wylicza jej z limitu tygodniowego. Claude udostępnia oba procenty.

## Gdy nie widać procentów

| Objaw | Sprawdź |
| --- | --- |
| W panelu jest `—` | Rozwiń widżet. Jeśli prosi o logowanie, kliknij go i zaloguj się w Falkonie. Jeśli jest napis „Usługa widgetu nie działa”, sprawdź usługę poleceniem poniżej. |
| Widać „Przeglądarka jest otwarta” po zamknięciu jednego okna | Falkon może mieć jeszcze inne okno tego profilu. Kliknij **Zakończ logowanie** w widżecie. |
| Widać „Wstrzymano podczas pełnego ekranu” | To oczekiwane podczas gry. Wyjdź z trybu pełnoekranowego i poczekaj około 15 sekund. |
| Widać „Oczekiwanie na stan pełnego ekranu z KDE” | Skrypt KWin nie przesłał jeszcze stanu. Uruchom `bash scripts/install.sh`; jeśli nadal nie działa, wyloguj się i zaloguj ponownie do KDE. |
| W szczegółach ChatGPT przy sesji jest „brak danych” | Ta strona ChatGPT nie pokazuje obecnie procentu sesji. Limit tygodniowy powinien być nadal widoczny. |
| Po aktualizacji kodu panel nadal pokazuje stary napis | Wykonaj kroki z sekcji „Aktualizacja” poniżej. |

Stan usługi i jej ostatnie komunikaty:

```bash
systemctl --user status limity-ai-widget.service
journalctl --user -u limity-ai-widget.service -n 50 --no-pager
```

Test bieżącego stanu, który nie uruchamia przeglądarki:

```bash
python3 scripts/check_live.py
```

Test z ponownym odczytem obu stron:

```bash
python3 scripts/check_live.py --refresh
```

Wariant `--refresh` sam odmawia odczytu podczas pełnego ekranu oraz gdy dedykowany Falkon pozostaje otwarty. Wynik `GREEN` oznacza, że są dostępne trzy procenty: tygodniowy ChatGPT oraz sesja i tydzień Claude. Osobna sesja ChatGPT nie jest warunkiem tego testu.

## Aktualizacja i usunięcie

Po zmianie kodu uruchom instalator ponownie i zrestartuj usługę, aby wczytała nowy kod Pythona:

```bash
bash scripts/install.sh
systemctl --user restart limity-ai-widget.service
```

Jeśli zmienił się wygląd widżetu, a panel nadal pokazuje starą wersję, przeładuj panel poza grą:

```bash
systemctl --user restart plasma-plasmashell.service
```

Panel może na moment zniknąć i wrócić. Samo przeładowanie nie otwiera okna logowania. Usługa wskazuje na **aktualną ścieżkę katalogu projektu**; po przeniesieniu projektu uruchom instalator z nowego miejsca.

Aby usunąć usługę i pakiety KDE:

```bash
bash scripts/uninstall.sh
```

Skrypt usuwający **zachowuje** lokalny profil przeglądarki i zapisane w nim sesje. Domyślnie znajdują się w `~/.local/share/limity-ai-widget`. Usuń ten katalog osobno tylko wtedy, gdy chcesz skasować również te dane. Konfiguracja usługi z lokalnym tokenem pozostaje w `~/.config/limity-ai-widget`.

## Prywatność, zasoby i ograniczenia

Falkon i niewidoczny czytnik Qt WebEngine korzystają z osobnego profilu. Nie używają profili Firefoksa, Brave ani Vivaldiego. Do widżetu trafiają odczytane procenty, czasy resetu, stan odczytu i godzina ostatniego odczytu; hasła wpisujesz bezpośrednio na stronach usług. Widżet łączy się z czytnikiem przez lokalny adres `127.0.0.1` i token zapisany w plikach użytkownika.

Na tym komputerze, przed zalogowaniem, niewidoczny czytnik zużywał około **183 MiB PSS** i 0,01 s CPU przez 5 s bezczynności. Falkon z dwiema otwartymi stronami zużywał około **1,1 GiB PSS**, dlatego jest uruchamiany tylko na żądanie. Zużycie po zalogowaniu może się różnić.

Projekt odczytuje tekst widocznych stron Usage, bez korzystania z API do limitów kont osobistych. Zmiana układu stron może wymagać poprawienia parsera. Wartości są ostatnim udanym odczytem, więc między odświeżeniami mogą być nieaktualne. Szczegóły implementacji są w [dokumentacji technicznej](docs/ARCHITECTURE.md).
