from pathlib import Path
from insider_llm_detection import ci

FIXTURES = Path(__file__).parent / "fixtures"

def test_fixture_episodes_rederive_exactly(capsys):
    # Every committed real episode must re-derive to its stored parser fields. A failure
    # here means a parser change altered a label on real data — look at the printout
    # before touching expected.json (a new not_logged must be verified by hand).
    assert ci.cmd_fixture_check(FIXTURES) == 0, capsys.readouterr().out
