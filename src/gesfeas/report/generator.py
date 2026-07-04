import os
from datetime import datetime
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from gesfeas.scenario.models import ScenarioResult
from gesfeas.input.models import SiteParameters
from gesfeas.production.models import ProductionResult

# Display symbol per currency code. Unknown codes fall back to "<CODE> " as a prefix.
CURRENCY_SYMBOLS = {"USD": "$", "TRY": "₺", "EUR": "€"}


def currency_symbol(currency_code: str) -> str:
    """Return the display symbol/prefix for a currency code (config-driven, not hardcoded)."""
    return CURRENCY_SYMBOLS.get(currency_code.upper(), f"{currency_code} ")


def generate_report_html(
    scenario_result: ScenarioResult,
    site: SiteParameters,
    consumption_df: pd.DataFrame,
    production: ProductionResult,
) -> str:
    """
    Renders the Jinja2 template with the given feasibility inputs and results.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(current_dir, "templates")

    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("feasibility_report.html")

    # Prepare monthly consumption data from consumption_df
    # Assuming consumption_df has 'consumption_kwh' column and is indexed by month or has 12 rows
    # We will format it nicely for the template.
    # If the dataframe has a datetime index, group by month.
    # The requirement is that consumption_df can be used to generate monthly consumption.
    
    # We will extract monthly values
    monthly_consumption = []
    if "consumption_kwh" in consumption_df.columns:
        if isinstance(consumption_df.index, pd.DatetimeIndex):
            monthly_sums = consumption_df["consumption_kwh"].resample("ME").sum()
            total_consumption = monthly_sums.sum()
            for idx, val in monthly_sums.items():
                monthly_consumption.append({
                    "month": idx.strftime("%B %Y"),
                    "consumption": val
                })
        else:
            total_consumption = consumption_df["consumption_kwh"].sum()
            for i, val in enumerate(consumption_df["consumption_kwh"]):
                monthly_consumption.append({
                    "month": f"Ay {i+1}",
                    "consumption": val
                })
    else:
        # Fallback if structure is different
        total_consumption = 0
        monthly_consumption = [{"month": "N/A", "consumption": 0}]

    report_date = datetime.now().strftime("%d.%m.%Y")

    html_content = template.render(
        scenario_result=scenario_result,
        site=site,
        production=production,
        monthly_consumption=monthly_consumption,
        total_consumption=total_consumption,
        report_date=report_date,
        currency_symbol=currency_symbol(scenario_result.pv_only.currency),
    )

    return html_content


def generate_report_pdf(html_content: str, output_path: str) -> str:
    """
    Converts rendered HTML string to PDF using WeasyPrint.
    Returns the absolute path to the generated PDF.
    """
    abs_output_path = os.path.abspath(output_path)
    HTML(string=html_content).write_pdf(abs_output_path)
    return abs_output_path


def generate_full_report(
    scenario_result: ScenarioResult,
    site: SiteParameters,
    consumption_df: pd.DataFrame,
    production: ProductionResult,
    output_path: str,
) -> str:
    """
    Convenience function that generates HTML and saves as PDF in one go.
    """
    html_content = generate_report_html(
        scenario_result=scenario_result,
        site=site,
        consumption_df=consumption_df,
        production=production,
    )
    return generate_report_pdf(html_content, output_path)
