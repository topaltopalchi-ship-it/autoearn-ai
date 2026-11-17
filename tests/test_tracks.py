import pytest

from autoearn.tracks import get_track, list_tracks, track_matches_category


def test_priority_tracks_put_playtesting_and_puzzles_first():
    tracks = list_tracks()
    assert [track.key for track in tracks[:3]] == [
        "game_playtesting", "puzzle_solving", "iq_reasoning"
    ]
    assert [track.priority for track in tracks] == sorted(
        track.priority for track in tracks
    )


@pytest.mark.parametrize(
    ("key", "category"),
    [
        ("game_playtesting", "games_competitions"),
        ("puzzle_solving", "games_competitions"),
        ("iq_reasoning", "games_competitions"),
        ("bug_testing", "freelancing_services"),
        ("ai_data_tasks", "surveys_microtasks"),
    ],
)
def test_track_matches_its_parent_category(key, category):
    assert track_matches_category(key, category)


def test_track_cannot_be_used_under_an_unrelated_category():
    assert not track_matches_category("game_playtesting", "surveys_microtasks")
    assert not track_matches_category("unknown_track", "games_competitions")


def test_unknown_track_is_not_silently_mapped():
    assert get_track("made_up_track") is None


@pytest.mark.parametrize(
    ("title", "category", "expected"),
    [
        ("حل یک معمای منطقی", "games_competitions", "puzzle_solving"),
        ("آزمون هوش و استدلال", "games_competitions", "iq_reasoning"),
        ("گزارش باگ در برنامه", "freelancing_services", "bug_testing"),
        ("تست نرم افزار موبایل", "freelancing_services", "software_qa"),
        ("برچسب گذاری داده", "surveys_microtasks", "ai_data_tasks"),
        ("ماموریت خرد آنلاین", "surveys_microtasks", "microtasks"),
        ("پروژه فریلنسری طراحی", "freelancing_services", "freelance_projects"),
    ],
)
def test_track_inference_supports_persian_titles(title, category, expected):
    from autoearn.tracks import infer_track_from_text
    assert infer_track_from_text(title, "", category) == expected


def test_track_inference_keeps_ambiguous_titles_unassigned():
    from autoearn.tracks import infer_track_from_text
    assert infer_track_from_text(
        "پازل و آزمون هوش", "", "games_competitions"
    ) == ""


def test_human_testing_tracks_are_not_marked_as_automatable():
    assert get_track("game_playtesting").execution_guidance == "human_required"
    assert get_track("software_qa").execution_guidance == "human_required"
    assert get_track("skill_competitions").execution_guidance == "official_api_only"
