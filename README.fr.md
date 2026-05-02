[English](README.md) | [中文](README.zh-CN.md) | [Français](README.fr.md)

<p align="center">
  <img src="assets/yuxiang-code-logo.svg" width="520" alt="Logo YuXiang Code">
</p>

<h1 align="center">YuXiang Code</h1>

<p align="center">
  <strong>Un agent autonome, c'est simplement un LLM + des outils + une boucle.</strong>
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="DeepSeek" src="https://img.shields.io/badge/DeepSeek-API-0F172A">
  <img alt="OpenAI compatible" src="https://img.shields.io/badge/API-OpenAI--compatible-111827">
  <img alt="Streaming SSE" src="https://img.shields.io/badge/Streaming-SSE-2563EB">
  <img alt="Local CLI" src="https://img.shields.io/badge/Run-Local%20CLI-4B5563">
  <img alt="Tools" src="https://img.shields.io/badge/Tools-bash%20%7C%20read%20%7C%20write%20%7C%20edit-047857">
</p>

<p align="center">
  Un petit agent de code inspectable pour les personnes qui preferent les fichiers simples, les appels d'outils visibles et les boucles sobres qui fonctionnent vraiment.
</p>

---

## Philosophy

| Choix | Raison |
|---|---|
| <span style="color:#d73a49"><strong>No</strong></span> Plan Mode | Utilisez plutot un fichier `PLAN.md`. Il est visible, versionnable et partageable entre conversations. |
| <span style="color:#d73a49"><strong>No</strong></span> MCP integration | Les descriptions d'outils consomment du budget de contexte. Les outils CLI et les README sont charges via `bash` seulement quand c'est necessaire. |
| <span style="color:#d73a49"><strong>No</strong></span> Sub-agents | Un agent cache dans un autre agent cache reduit l'observabilite. Utilisez `bash` pour lancer un autre processus quand il en faut un. |
| <span style="color:#d73a49"><strong>No</strong></span> `maxSteps` ceremony | La boucle doit se terminer naturellement quand la tache est terminee. Ajoutez une limite seulement lorsqu'un vrai probleme apparait. |
| <span style="color:#d73a49"><strong>No</strong></span> permission theater | Une fois qu'un agent peut ecrire et executer du code, les fausses confirmations ne sont pas un modele de securite. Gardez la surface locale et inspectable. |

YuXiang Code est volontairement petit. Il n'essaie pas de devenir un systeme d'exploitation pour agents. Il garde la boucle centrale visible :

```text
user -> LLM -> tool call -> tool result -> LLM -> done
```

Le but n'est pas de cacher la complexite derriere un autre framework. Le but est de rendre l'agent assez comprehensible pour pouvoir le deboguer pendant qu'il tourne.

## Ce que c'est

- Une conversation terminal en streaming avec appels d'outils visibles.
- Des outils locaux pour `bash`, `read`, `write` et `edit`.
- Des controles manuels du contexte pour inspecter, reduire, sauvegarder et reecrire le contexte exact du modele.
- Une CLI locale, pas une plateforme d'agents hebergee.

C'est le produit. Le reste doit meriter sa place.

## Demarrage rapide

```powershell
$env:DEEPSEEK_API_KEY="your-key"
python -m pip install -e .
python .\code_agent.py
```

## Commandes

Seules les entrees prefixees par `/` sont interpretees comme des commandes. `history` est un message normal ; `/history` ouvre le panneau du contexte actif.

```text
/help              afficher les commandes
/models            afficher les noms de modeles DeepSeek integres
/history           afficher le contexte actif complet du modele
/context           alias de /history
/clear             vider le contexte et l'historique de saisie
/keep [n]          garder seulement les n derniers messages de contexte
/drop INDEX        supprimer un message du contexte
/set INDEX text    remplacer un message du contexte
/system text       remplacer le system prompt
/save              sauvegarder le contexte dans .agent_context.json
/load              charger le contexte depuis .agent_context.json
/model [name]      afficher ou changer le modele
/exit              quitter
```

## Structure du projet

```text
.
|-- code_agent.py
|-- pyproject.toml
|-- assets/
`-- src/
    `-- mini_code_agent/
        |-- api.py
        |-- app.py
        |-- config.py
        |-- models.py
        |-- prompt.py
        |-- session.py
        |-- tools.py
        `-- ui.py
```

## License

MIT
