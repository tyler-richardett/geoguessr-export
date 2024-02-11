from geoguessr_export.geoguessr import Geoguessr
from geoguessr_export.notion import Notion


def main():
    geoguessr = Geoguessr()
    daily_challenges = geoguessr.get_daily_challenges()

    notion = Notion()
    notion.add_daily_challenges(daily_challenges)
