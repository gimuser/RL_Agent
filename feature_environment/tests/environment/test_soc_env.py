import numpy as np

from feature_environment.environment.soc_env import SOCEnv
from feature_environment.gym.action_space import SocAction
from feature_environment.soc.playbook import Playbook


def test_reset_is_seeded_and_valid():
    env = SOCEnv(max_steps=3)
    first, _ = env.reset(seed=42)
    second, _ = env.reset(seed=42)
    assert env.observation_space.contains(first)
    np.testing.assert_array_equal(first, second)


def test_step_uses_gymnasium_contract_and_truncates_at_time_limit():
    env = SOCEnv(max_steps=2)
    observation, _ = env.reset(seed=7)
    for step in range(2):
        observation, reward, terminated, truncated, info = env.step(SocAction.INVESTIGATE)
        assert env.observation_space.contains(observation)
        assert isinstance(reward, float)
        assert terminated is False
        assert truncated is (step == 1)
        assert "outcome" in info


def test_containing_a_malicious_alert_is_rewarded_more_than_ignoring_it():
    env = SOCEnv()
    env.reset(seed=1)
    alert = env.simulator.current_alert
    alert.is_malicious = True
    alert.severity = 4
    env.simulator.playbooks = (Playbook("test-playbook", (alert.severity,), 1.0),)
    _, contain_reward, *_ = env.step(SocAction.CONTAIN)
    env.reset(seed=1)
    alert = env.simulator.current_alert
    alert.is_malicious = True
    alert.severity = 4
    _, ignore_reward, *_ = env.step(SocAction.IGNORE)
    assert contain_reward > ignore_reward
