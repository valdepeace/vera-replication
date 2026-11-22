"""Modelo mixto del éxito sustantivo: condición y modelo de lenguaje como efectos fijos,
método focal como efecto aleatorio."""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

from vera.types import AuditOutcome, Condition


@dataclass
class MixedResult:
    method: str
    log_odds: float
    se: float
    odds_ratio: float


def _frame(records):
    import pandas as pd

    rows = [{"y": int(r.accepted and r.audit is AuditOutcome.REAL),
             "repair": int(r.config.condition is Condition.REPAIR),
             "model": r.config.model.name, "method": r.config.task.id}
            for r in records if r.valid]
    return pd.DataFrame(rows)


def _result(method: str, log_odds: float, se: float) -> MixedResult | None:
    if not (math.isfinite(log_odds) and math.isfinite(se) and se > 0):
        return None
    return MixedResult(method=method, log_odds=log_odds, se=se, odds_ratio=math.exp(log_odds))


def _bayes(df, formula: str) -> MixedResult | None:
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

    model = BinomialBayesMixedGLM.from_formula(formula, {"method": "0 + C(method)"}, df)
    fit = model.fit_vb()
    i = list(model.exog_names).index("repair")
    return _result("BinomialBayesMixedGLM (VB)", float(fit.fe_mean[i]), float(fit.fe_sd[i]))


def _gee(df, formula: str) -> MixedResult | None:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    fit = smf.gee(formula, groups="method", data=df, family=sm.families.Binomial(),
                  cov_struct=sm.cov_struct.Exchangeable()).fit()
    return _result("GEE binomial (intercambiable, por método)",
                   float(fit.params["repair"]), float(fit.bse["repair"]))


def mixed_model(records) -> MixedResult:
    """Efecto de la reparación en log-odds. Se intenta BinomialBayesMixedGLM y, si no
    converge o no encaja, GEE binomial con correlación intercambiable agrupando por método."""
    df = _frame(records)
    formula = "y ~ repair" + (" + C(model)" if df["model"].nunique() > 1 else "")
    for fit in (_bayes, _gee):
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # un aviso de convergencia descarta el ajuste
            try:
                result = fit(df, formula)
            except Exception:  # noqa: BLE001 - cualquier fallo del ajuste pasa al siguiente
                result = None
        if result is not None:
            return result
    raise RuntimeError("ni el modelo mixto bayesiano ni el GEE pudieron ajustarse")
