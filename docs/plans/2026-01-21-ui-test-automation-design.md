# UI Test Automation Design

## Problem

Current test coverage for UI code is low:
- `client/ui.py`: 20% coverage
- `client/main.py`: 0% coverage

Manual testing is required to verify UI behavior, which is slow and error-prone.

## Goals

- Increase code coverage to 95% for ui.py and main.py
- Catch regressions automatically
- Test end-to-end game flows
- Fast feedback during development + comprehensive CI testing

## Solution

Pytest fixtures with questionary mocking, plus integration tests with real server.

## Architecture

### Testing Pyramid

1. **Unit tests with mocks** (fast, many) - Test individual functions with mocked questionary/rich
2. **Integration tests with real server** (slower, fewer) - Test complete flows with actual server

### Test Infrastructure

#### Questionary Mocking Fixture

```python
@pytest.fixture
def mock_ui_inputs(monkeypatch):
    """Fixture to script questionary inputs for UI testing."""
    responses = []
    call_index = [0]

    def scripted_select(*args, **kwargs):
        mock = MagicMock()
        mock.ask.return_value = responses[call_index[0]]
        call_index[0] += 1
        return mock

    monkeypatch.setattr("questionary.select", scripted_select)
    monkeypatch.setattr("questionary.text", scripted_select)

    def set_responses(resp_list):
        responses.clear()
        responses.extend(resp_list)
        call_index[0] = 0

    return set_responses
```

#### Additional Fixtures

- `mock_network` - Mock NetworkThread with scripted poll responses
- `mock_game_state` - Create GameState with configurable players, locations, phases
- `mock_server_responses` - Script full server conversation sequences

## Components

### 1. UI Function Tests (tests/unit/test_ui.py)

**Print functions** - Mock rich.console.Console and verify calls:
- `print_main_menu()`, `print_header()`, `print_lobby()`
- `print_shop()`, `print_round_results()`, `print_game_over()`
- `print_escape_prompt()`, `print_escape_result()`
- `print_location_choice_prompt()`, `print_connecting()`
- `print_error()`, `print_info()`, `clear_screen()`

**Input functions** - Test each questionary-based function:
- `get_player_name()` - text input
- `get_player_count()` - select 2-6
- `get_location_choice()` - select from locations
- `get_escape_choice()` - select escape option
- `get_shop_choice()` - select passive or skip
- `get_host_name()`, `get_game_name()`, `get_server_address()`
- `select_lan_game()` - select from discovered games

**Edge cases to test:**
- Empty player lists
- Missing data in state
- Player alive/dead states
- Various passive combinations

### 2. GameClient Tests (tests/unit/test_game_client.py)

**Helper method tests:**
- `_wait_for_message()` - returns data on match, None on connection lost
- `_poll_all_networks()` - handles multiple connections
- `_handle_message()` - routes messages correctly

**Game mode entry tests:**
- `_play_single_player()` - mock server startup, verify connection flow
- `_play_local_multiplayer()` - verify multiple network threads created
- `_host_online_game()` - verify LAN broadcasting started
- `_join_online_game()` - verify scan and connect flow

**Game loop tests:**
- Phase transitions (LOBBY → CHOOSING → RESULTS → GAME_OVER)
- Shop phase handling
- Escape phase handling
- Connection loss handling
- Timeout scenarios

**Hot-seat multiplayer tests:**
- 2-6 player scenarios
- Multiple network thread management
- Player turn handling

### 3. Integration Tests (tests/integration/test_game_flows.py)

```python
@pytest.fixture
def game_server():
    """Start real server for integration tests."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", "18900"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(0.5)
    yield "ws://127.0.0.1:18900"
    proc.terminate()
```

**Key flows:**
- Single player: menu → name → play rounds → game over
- Host online: menu → setup → lobby → start
- Join online: menu → scan/address → join → play
- Hot-seat: menu → player count → names → play

Mark with `@pytest.mark.slow` for selective running.

## File Structure

```
tests/
  conftest.py              # Add mock_ui_inputs, mock_network fixtures
  unit/
    test_ui.py             # Expand existing (target: 95% of ui.py)
    test_game_client.py    # New file (target: 95% of main.py)
  integration/
    test_game_flows.py     # New file - end-to-end with real server
```

## Coverage Targets

| File | Current | Target |
|------|---------|--------|
| client/ui.py | 20% | 95% |
| client/main.py | 0% | 95% |
| Overall | 65% | 90%+ |

## CI Configuration

**Test markers:**
```python
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (run with pytest -m slow)",
]
```

**CI strategy:**
- Fast tests on every push: `pytest -m "not slow"`
- Full suite on PR merge: `pytest`

## Implementation Tasks

### Task 1: Test Fixtures
Create reusable fixtures in `tests/conftest.py`:
- `mock_ui_inputs` - Script questionary responses
- `mock_network` - Mock NetworkThread with scripted responses
- `mock_game_state` - Configurable GameState factory
- `mock_console` - Mock rich console for output verification

### Task 2: UI Function Tests
Expand `tests/unit/test_ui.py` to test all functions in ui.py:
- Print functions with mocked console
- Input functions with mocked questionary
- Edge cases and error states
- Target: 95% coverage of ui.py

### Task 3: GameClient Unit Tests
Create `tests/unit/test_game_client.py`:
- Helper method tests
- Game mode entry tests (mocked network)
- Game loop and phase transition tests
- Error handling and edge cases
- Target: 95% coverage of main.py

### Task 4: Integration Tests
Create `tests/integration/test_game_flows.py`:
- Real server fixture
- Single player complete flow
- Online host/join flows
- Hot-seat multiplayer flow
- Mark with @pytest.mark.slow

### Task 5: CI Updates
- Add slow marker to pytest configuration
- Update CI workflow to run fast tests on push
- Run full suite on PR merge
