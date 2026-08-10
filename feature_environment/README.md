# SOC Gymnasium Environment

Environment Gymnasium de simulation de centre opérationnel de sécurité (SOC) pour entraîner un agent de reinforcement learning à trier les alertes SIEM et déclencher des actions SOAR.

## Installation

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
pytest -q
```

## Utilisation

```python
from feature_environment.environment import SOCEnv
from feature_environment.gym.action_space import SocAction

env = SOCEnv(max_steps=100)
observation, info = env.reset(seed=42)

while True:
    action = env.action_space.sample()  # ou action produite par la politique RL
    observation, reward, terminated, truncated, info = env.step(action)
    if terminated or truncated:
        break
```

Les actions sont : `IGNORE`, `INVESTIGATE`, `CONTAIN`, `CLOSE_FALSE_POSITIVE` et `ESCALATE`.
L'observation est un vecteur normalisé de 11 valeurs (caractéristiques de l'alerte
courante, file SIEM, charge analyste, incidents et métriques SOC). La vérité terrain
(`is_malicious`) reste interne au simulateur afin d'éviter toute fuite vers l'agent.

Un épisode est limité par `max_steps` et retourne alors `truncated=True`, conformément
au contrat Gymnasium. La graine passée à `reset(seed=...)` rend la simulation
reproductible.
