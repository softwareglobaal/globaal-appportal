Besluit: **alleen de voorbereider live zetten is niet veilig**. De oude Mac-wacht kan een taak na mislukte JPG-omzetting afvinken; door de unieke sleutel komt die niet terug. W4 blijft zichtbaar als `let_op` met “alleen HEIC, geen JPG” ([wacht](/Users/user2025/dev/_w4-p3-fototaak/mijnagents-runner/mac/icloud_wacht.py:727), [voorbereider](/Users/user2025/dev/_w4-p3-fototaak/mijnagents-runner/werfverslag_voorbereider.py:884)).

X3 en X4 zijn correct verwerkt. De X4-test zou op de oude code falen, maar ik kon dat niet uitvoeren: `pytest` ontbreekt en de omgeving staat geen tijdelijke testmap toe. Syntaxis en code-diff zijn gecontroleerd.

Open: tests draaien en de Mac-wacht met sudo uitrollen vóór deze voorbereider live gaat. Niets gepusht of uitgerold.

NIET AKKOORD