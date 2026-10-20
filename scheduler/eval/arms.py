"""The arms being compared. Each takes a scenario on a freshly reset sandbox and returns its
outcome; the episode wrapper collects everything else from the sandbox's records.

(a) free/busy finder               scheduler.eval.baselines.free_busy"""
from scheduler.eval.baselines import free_busy

ARMS = {"a": free_busy}
