import sim
import s5_policy

STEP = "0.5"
CASES = [
    ("Human drivers only", "y_av_0", {}),
    ("25% automated vehicles", "y_av_25", {"av_share": 0.25}),
    ("50% automated vehicles", "y_av_50", {"av_share": 0.5}),
    ("100% automated vehicles", "y_av_100", {"av_share": 1.0}),
]

plain_run = sim.run


def fine_run(tag, trips_file, extra=()):
    return plain_run(tag, trips_file, list(extra) + ["--step-length", STEP])


if __name__ == "__main__":
    sim.run = fine_run
    s5_policy.main(CASES, "s5_av")