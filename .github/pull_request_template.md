## Qué cambia

<!-- Una o dos frases. Si cierra un issue, escribe "Cierra #123". -->

## Por qué

<!-- El problema que resuelve. Si el cambio es evidente, borra esta sección. -->

## Cómo lo probaste

<!--
Los comandos que ejecutaste y qué viste. Si tocaste app/ui/ o
app/workers/, que no tienen pruebas automáticas (ADR-0002), di qué
verificaste ejecutando la aplicación.
-->

## Antes de pedir revisión

- [ ] `pytest -m "not smtp"` pasa completo
- [ ] Las funciones nuevas tienen prueba, o expliqué abajo por qué no
- [ ] El texto que ve la persona usuaria está en español; el código, los
      comentarios y los mensajes de commit en inglés
- [ ] `app/core/` y `app/cli.py` siguen sin importar Qt
- [ ] Si toqué dependencias: ejecuté `python scripts/vendor.py` y sumé al
      commit `vendor/`, `SHA256SUMS.txt` y `requirements-core.lock`
- [ ] Si cambié una decisión de arquitectura: escribí un ADR nuevo en
      `docs/adr/` y marqué el anterior como superado, sin editar su cuerpo

## Notas para quien revise

<!-- Dudas abiertas, alternativas que descartaste, o partes que te gustaría
que se miren con más atención. Opcional. -->
