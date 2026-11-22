Yo la llamaría Loom VERA.

# LOOM VERA

Validation · Execution · Repair · Audit

POC de validación, ejecución, reparación y auditoría de código generado por LLM locales.

Me gusta porque recoge las cuatro piezas que queremos investigar, incluida la más importante del paper: comprobar que un resultado correcto no sea un falso positivo.

VERA medirá primero el ciclo validate–repair. ODD + Gauntlet quedan como comparadores posteriores, una vez establecidas las líneas base de VERA-01 y VERA-02.

Lo organizaría así:

```
poc-loom-vera/
        ├── docs/
        │   ├── paper/
        │   │   └── validate-repair-uned-2026.pdf
        │   ├── research.md
        │   └── findings.md
        ├── configs/
        ├── benchmarks/
        ├── results/
        └── README.md
```

## Plan acordado

- **VERA-01:** adaptar el método a generación de tests unitarios para proyectos Python y JavaScript/Node. Comparar generación directa con reparación iterativa usando el mismo harness y auditar que cada test aceptado ejercita el método focal.
- **VERA-02:** validar externamente el flujo en una selección fija de tareas Python y JavaScript de DeepSWE, manteniendo fijo el verificador y el harness. Un subconjunto o un harness modificado se reportará como experimento VERA, no como puntuación oficial del benchmark.
- **ODD + Gauntlet:** comparación posterior, después de establecer ambas líneas base.

Terminal-Bench queda como posible prueba posterior de uso general de terminal, no como la evaluación inicial de código.

Así el proyecto tiene nombre propio, mantiene el documento original como referencia y nos permite añadir experimentos sin convertir Loom en otro festival de frameworks.
