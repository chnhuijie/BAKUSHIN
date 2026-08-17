import random

last_quotes = {"dailies": None, "tt": None}

DAILIES_QUOTES = [
    "Everyone! There's only a few more hours to do dailies! Let's all BAKUSHIN to it!! BAKUSHIIINNN!!",
    "You, hold it right there! As long as I am the class president - I won't allow you to skip out on doing dailies!",
    "A model student never neglects their daily training! Let's hit the track, full speed ahead!! BAKUSHIN!!",
    "Dailies are the foundation MAX SPEED! Don't slack off now, or I'll have to lecture you!",
    "Wa-ha-ha! Only a true sprinter finishes their dailies before the deadline! Are you ready? Set? BAKUSHIN!"
]

TT_QUOTES = [
    "It's only a few more hours until Team Trials begins tallying! Let's BAKUSHIN towards a new highscore! BAKUSHIN-SHIN!!!",
    "There's no time to waste - the TT tally is closing soon, get your runs in before it's too late!",
    "The class president commands you to push your limits! Secure your Team Trials rank with a resounding BAKUSHIN!",
    "Tallying is fast approaching! If you don't run now, you'll be left in the dust! Sprint to the finish!",
    "Hear that? That's the sound of the Team Trials deadline! Let's show everyone the results of our lightning-fast training!"
]

def get_quote(quote_type):
    global last_quotes
    pool = DAILIES_QUOTES if quote_type == "dailies" else TT_QUOTES
    available = [q for q in pool if q != last_quotes[quote_type]]
    chosen = random.choice(available)
    last_quotes[quote_type] = chosen
    return chosen
