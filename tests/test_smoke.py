from radar import config


def test_paths_exist_under_root():
    assert config.DATA.parent == config.ROOT
    assert config.START_QUARTER < config.END_QUARTER
