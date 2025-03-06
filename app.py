import marimo

__generated_with = "0.11.0"
app = marimo.App(width="medium", app_title="Differential Expression Viewer")


@app.cell
def _(mo):
    mo.md(r"""# Differential Expression Viewer""")
    return


@app.cell
def _():
    # Load the marimo library in a dedicated cell for efficiency
    import marimo as mo
    return (mo,)


@app.cell
def _():
    # If the script is running in WASM (instead of local development mode), load micropip
    import sys
    if "pyodide" in sys.modules:
        import micropip
        running_in_wasm = True
    else:
        micropip = None
        running_in_wasm = False
    return micropip, running_in_wasm, sys


@app.cell
async def _(micropip, mo, running_in_wasm):
    with mo.status.spinner("Loading dependencies"):
        # If we are running in WASM, some dependencies need to be set up appropriately.
        # This is really just aligning the needs of the app with the default library versions
        # that come when a marimo app loads in WASM.
        if running_in_wasm:
            print("Installing via micropip")
            # Downgrade plotly to avoid the use of narwhals
            await micropip.install("plotly<6.0.0")
            await micropip.install("ssl")
            micropip.uninstall("urllib3")
            micropip.uninstall("httpx")
            await micropip.install("urllib3==2.3.0")
            await micropip.install("botocore==1.36.23")
            await micropip.install("jmespath==1.0.1")
            await micropip.install("s3transfer==0.11.3")
            await micropip.install("boto3==1.36.23")
            await micropip.install("aiobotocore==2.20.0")
            await micropip.install("cirro[pyodide]>=1.2.16")

        from io import StringIO, BytesIO
        from queue import Queue
        from time import sleep
        from typing import Dict, Optional
        import plotly.express as px
        import pandas as pd
        import numpy as np
        from functools import lru_cache
        import base64
        from urllib.parse import quote_plus

        from cirro import DataPortalLogin
        from cirro.services.file import FileService
        from cirro.sdk.file import DataPortalFile
        from cirro.config import list_tenants

        # A patch to the Cirro client library is applied when running in WASM
        if running_in_wasm:
            from cirro.helpers import pyodide_patch_all
            pyodide_patch_all()
    return (
        BytesIO,
        DataPortalFile,
        DataPortalLogin,
        Dict,
        FileService,
        Optional,
        Queue,
        StringIO,
        base64,
        list_tenants,
        lru_cache,
        np,
        pd,
        px,
        pyodide_patch_all,
        quote_plus,
        sleep,
    )


@app.cell
def _(mo):
    # Get and set the query parameters
    query_params = mo.query_params()
    return (query_params,)


@app.cell
def _(list_tenants):
    # Get the tenants (organizations) available in Cirro
    tenants_by_name = {i["displayName"]: i for i in list_tenants()}
    tenants_by_domain = {i["domain"]: i for i in list_tenants()}


    def domain_to_name(domain):
        return tenants_by_domain.get(domain, {}).get("displayName")


    def name_to_domain(name):
        return tenants_by_name.get(name, {}).get("domain")
    return (
        domain_to_name,
        name_to_domain,
        tenants_by_domain,
        tenants_by_name,
    )


@app.cell
def _(mo):
    mo.md(r"""## Load Data""")
    return


@app.cell
def _(mo, query_params):
    # Give the user the option to load data from a URL or from Cirro
    # If a Cirro domain is provided in query params, then that will be the default
    data_source_ui = mo.ui.radio(
        {
            "URL": "url",
            "Cirro": "cirro"
        },
        label="Read Data From",
        value=("Cirro" if query_params.get("domain") is not None else "URL")
    )
    data_source_ui
    return (data_source_ui,)


@app.cell
def _(mo):
    # Use a state element to update the DataFrame once it has been read in
    get_df, set_df = mo.state(None)
    return get_df, set_df


@app.cell
def _(data_source_ui, mo, query_params):
    # Stop execution if the user did not select the URL option
    mo.stop(data_source_ui.value != "url")

    # Let the user enter the URL
    url_ui = mo.ui.text(
        label="Load Data from URL (CSV)",
        placeholder="--",
        value=query_params.get("url", ""),
        on_change=lambda v: query_params.set("url", v)
    )
    url_ui
    return (url_ui,)


@app.cell
def _(pd, sep_ui, set_df, url_ui):
    # If the URL was provided, read it in
    if url_ui.value is not None and len(url_ui.value) > 0:
        set_df(pd.read_csv(url_ui.value, sep=dict(comma=",", tab="\t", space=" ")[sep_ui.value]))
    return


@app.cell
def _(mo):
    # Use a state element to manage the Cirro client object
    get_client, set_client = mo.state(None)
    return get_client, set_client


@app.cell
def _(data_source_ui, domain_to_name, mo, query_params, tenants_by_name):
    # If Cirro is not selected, stop any further execution of cells that depend on this output
    mo.stop(data_source_ui.value != "cirro")

    # Let the user select which tenant to log in to (using displayName)
    domain_ui = mo.ui.dropdown(
        options=tenants_by_name,
        value=domain_to_name(query_params.get("domain")),
        on_change=lambda i: query_params.set("domain", i["domain"]),
        label="Load Data from Cirro",
    )
    domain_ui
    return (domain_ui,)


@app.cell
def _(DataPortalLogin, domain_ui, get_client, mo):
    # If the user is not yet logged in, and a domain is selected, then give the user instructions for logging in
    # The configuration of this cell and the two below it serve the function of:
    #   1. Showing the user the login instructions if they have selected a Cirro domain
    #   2. Removing the login instructions as soon as they have completed the login flow
    if get_client() is None and domain_ui.value is not None:
        with mo.status.spinner("Authenticating"):
            # Use device code authorization to log in to Cirro
            cirro_login = DataPortalLogin(base_url=domain_ui.value["domain"])
            cirro_login_ui = mo.md(cirro_login.auth_message_markdown)
    else:
        cirro_login = None
        cirro_login_ui = None

    mo.stop(cirro_login is None)
    cirro_login_ui
    return cirro_login, cirro_login_ui


@app.cell
def _(cirro_login, set_client):
    # Once the user logs in, set the state for the client object
    set_client(cirro_login.await_completion())
    return


@app.cell
def _(data_source_ui, get_client, mo):
    # Get the Cirro client object (but only take action if the user selected Cirro as the input)
    client = get_client()
    mo.stop(client is None)
    mo.stop(data_source_ui.value != "cirro")
    return (client,)


@app.cell
def _():
    # Helper functions for dealing with lists of objects that may be accessed by id or name
    def id_to_name(obj_list: list, id: str) -> str:
        if obj_list is not None:
            return {i.id: i.name for i in obj_list}.get(id)


    def name_to_id(obj_list: list) -> dict:
        if obj_list is not None:
            return {i.name: i.id for i in obj_list}
        else:
            return {}
    return id_to_name, name_to_id


@app.cell
def _(client):
    # Set the list of projects available to the user
    projects = client.list_projects()
    projects.sort(key=lambda i: i.name)
    return (projects,)


@app.cell
def _(id_to_name, mo, name_to_id, projects, query_params):
    # Let the user select which project to get data from
    project_ui = mo.ui.dropdown(
        value=id_to_name(projects, query_params.get("project")),
        options=name_to_id(projects),
        on_change=lambda i: query_params.set("project", i)
    )
    project_ui
    return (project_ui,)


@app.cell
def _(client, mo, project_ui):
    # Stop if the user has not selected a project
    mo.stop(project_ui.value is None)

    # Get the list of datasets available to the user
    # Filter the list of datasets by type (process_id)
    datasets = [
        dataset
        for dataset in client.get_project_by_id(project_ui.value).list_datasets()
        if dataset.process_id in [
            "process-hutch-differential-expression-1_0",
            "process-hutch-differential-expression-custom-1_0",
            "differential-expression-table",
            "process-nf-core-differentialabundance-1_5"
        ]
    ]
    return (datasets,)


@app.cell
def _(datasets, id_to_name, mo, name_to_id, query_params):
    # Let the user select which dataset to get data from
    dataset_ui = mo.ui.dropdown(
        value=id_to_name(datasets, query_params.get("dataset")),
        options=name_to_id(datasets),
        on_change=lambda i: query_params.set("dataset", i)
    )
    dataset_ui
    return (dataset_ui,)


@app.cell
def _(client, dataset_ui, mo, project_ui):
    # Stop if the user has not selected a dataset
    mo.stop(dataset_ui.value is None)

    # Get the list of files within the selected dataset
    file_list = [
        file.name
        for file in (
            client
            .get_project_by_id(project_ui.value)
            .get_dataset_by_id(dataset_ui.value)
            .list_files()
        )
    ]
    return (file_list,)


@app.cell
def _(file_list, mo, query_params):
    # Let the user select which file to get data from
    file_ui = mo.ui.dropdown(
        value=(query_params.get("file") if query_params.get("file") in file_list else None),
        options=file_list,
        on_change=lambda i: query_params.set("file", i)
    )
    file_ui
    return (file_ui,)


@app.cell
def _(mo, query_params):
    # Let the user provide information about the file format
    sep_ui = mo.ui.dropdown(
        ["comma", "tab", "space"],
        value=query_params.get("sep", "comma"),
        label="Field Separator"
    )
    sep_ui
    return (sep_ui,)


@app.cell
def _(client, dataset_ui, file_ui, project_ui, sep_ui, set_df):
    # If the file was selected
    if file_ui.value is not None:
        # Read the table and set the state
        set_df(
            (
                client
                .get_project_by_id(project_ui.value)
                .get_dataset_by_id(dataset_ui.value)
                .list_files()
                .get_by_id(file_ui.value)
                # Set the delimiter used to read the file based on the menu selection
                .read_csv(sep=dict(comma=",", tab="\t", space=" ")[sep_ui.value])
            )
        )
    return


@app.cell
def _(get_df, mo):
    # Access the state element to get the DataFrame from either the URL or Cirro route
    df = get_df()
    mo.stop(df is None)
    return (df,)


@app.cell
def _():
    # Helper when trying to guess the right column in the input table to use
    def guess_column(l, options):
        for i in l:
            if isinstance(i, str) and i.lower() in options:
                return i
    return (guess_column,)


@app.cell
def _(df, guess_column, mo, query_params):
    # Let the user select parameters for the display
    params_ui = (
        mo.md("""
    ## Display Settings

    ### Input Data

    {pval_cname}<br>
    {max_pval}<br>
    {lfc_cname}<br>
    {min_lfc}<br>
    {abund_cname}<br>
    {abund_log}<br>
    {label_cname}<br>

    ### Display Labels

    {pval_label}<br>
    {lfc_label}<br>
    {abund_label}<br>

    ### Plot Settings

    {theme}
    {width}
    {height}
        """)
        .batch(
            pval_cname=mo.ui.dropdown(
                label="p-value:",
                options=df.columns,
                value=query_params.get(
                    'pval_cname',
                    guess_column(df.columns.values, ['pval', 'pvalue', 'p-value'])
                )
            ),
            max_pval=mo.ui.text(
                label="max p:",
                value=query_params.get("max_pval", "0.05")
            ),
            abund_cname=mo.ui.dropdown(
                label="abundance:",
                options=df.columns,
                value=query_params.get(
                    'abund_cname',
                    guess_column(df.columns.values, ['basemean', 'mean_abund', 'meanabund', 'base_mean'])
                )
            ),
            abund_log=mo.ui.checkbox(
                label="log-scale abundance",
                value=bool(query_params.get("abund_log", True))
            ),
            lfc_cname=mo.ui.dropdown(
                label="fold change:",
                options=df.columns,
                value=query_params.get(
                    'lfc_cname',
                    guess_column(df.columns.values, ['logfc', 'foldchange', 'fold_change', 'log_fold_change'])
                )
            ),
            min_lfc=mo.ui.text(
                label="min fold change",
                value=query_params.get("min_lfc", "2")
            ),
            label_cname=mo.ui.dropdown(
                label="gene name:",
                options=df.columns,
                value=query_params.get(
                    'label_cname',
                    guess_column(df.columns.values, ['gene_id', 'geneid', 'gene_name', 'genename'])
                )
            ),
            pval_label=mo.ui.text(
                value=query_params.get("pval_label", "p-value (-log10)")
            ),
            lfc_label=mo.ui.text(
                value=query_params.get("lfc_label", "Fold Change (log2)")
            ),
            abund_label=mo.ui.text(
                value=query_params.get("abund_label", "Mean Abundance (RPKM)")
            ),
            theme=mo.ui.dropdown(
                label="Theme:",
                options=["plotly", "plotly_white", "plotly_dark", "ggplot2", "seaborn", "simple_white", "none"],
                value=query_params.get("theme", "none")
            ),
            width=mo.ui.number(
                label="Width:",
                value=int(query_params.get("width", 600)),
                start=100,
                stop=2400,
                step=10
            ),
            height=mo.ui.number(
                label="Height:",
                value=int(query_params.get("height", 400)),
                start=100,
                stop=2400,
                step=10
            )
        )
    )
    mo.sidebar(params_ui)
    return (params_ui,)


@app.cell
def _(params_ui):
    # Map the params to a single dict for brevity
    params = params_ui.value
    return (params,)


@app.cell
def _(df, mo, np, params):
    max_pval = None
    min_lfc = None
    user_feedback = ""
    if df is not None:
        with mo.status.spinner("Preparing data"):
            prepared_df = df.copy()

            # Set any 0 pvalues to a minimum value (for plotting), and apply the -log10 transform
            min_pval = df.query(f'{params["pval_cname"]} > 0')[params["pval_cname"]].min()
            prepared_df = prepared_df.assign(**{
                "_neg_log10_pval": -prepared_df[params["pval_cname"]].clip(lower=min_pval).apply(np.log10)
            })

            # Set the thresholds for maximum pvalue and minimum fold change
            if params.get("max_pval") is not None:
                try:
                    max_pval = float(params["max_pval"])
                except:
                    user_feedback += f"Could not convert p-value threshold to a float ({params['max_pval']})\n\n"

            if params.get("min_lfc") is not None:
                try:
                    min_lfc = float(params["min_lfc"])
                except:
                    user_feedback += f"Could not convert fold change threshold to a float ({params['min_lfc']})\n\n"

            prepared_df = prepared_df.assign(
                passes_threshold=prepared_df.apply(
                    lambda r: (
                        ((max_pval is None) or (r[params["pval_cname"]] <= max_pval))
                        and
                        ((min_lfc is None) or (np.abs(r[params["lfc_cname"]]) >= min_lfc))
                    ),
                    axis=1
                )
            )

    else:
        prepared_df = None

    mo.md(user_feedback)
    return max_pval, min_lfc, min_pval, prepared_df, user_feedback


@app.cell
def _(mo, volcano_fig):
    if volcano_fig is not None:
        volcano_header = mo.md("## Volcano Plot")
    else:
        volcano_header = None

    volcano_header
    return (volcano_header,)


@app.cell
def _(df, max_pval, min_lfc, mo, np, params, prepared_df, px):
    if df is not None:
        with mo.status.spinner("Making plot"):
            volcano_fig = px.scatter(
                data_frame=prepared_df,
                x=params["lfc_cname"],
                y="_neg_log10_pval",
                labels={
                    "_neg_log10_pval": params["pval_label"],
                    params["lfc_cname"]: params["lfc_label"],
                    params["abund_cname"]: params["abund_label"],
                    "passes_threshold": "Passes Threshold",
                },
                color="passes_threshold",
                hover_name=params["label_cname"],
                hover_data=[params["pval_cname"], params["abund_cname"]],
                template=params["theme"],
                width=params["width"],
                height=params["height"]
            )
            volcano_fig.update_layout(
                plot_bgcolor="white",  # Set plot background color
                paper_bgcolor="white", # Set paper background color
                xaxis=dict(
                    showgrid=True,  # Show grid lines on the x-axis
                    gridcolor='lightgray'  # Set the color of the grid lines
                ),
                yaxis=dict(
                    showgrid=True,  # Show grid lines on the y-axis
                    gridcolor='lightgray'  # Set the color of the grid lines
                )
            )
            if max_pval is not None:
                volcano_fig.add_hline(-np.log10(max_pval), line_dash="dash", line_color="grey", opacity=0.5)
            if min_lfc is not None:
                volcano_fig.add_vline(min_lfc, line_dash="dash", line_color="grey", opacity=0.5)
                volcano_fig.add_vline(-min_lfc, line_dash="dash", line_color="grey", opacity=0.5)
    else:
        volcano_fig = None

    volcano_fig
    return (volcano_fig,)


@app.cell
def _(ma_fig, mo):
    if ma_fig is not None:
        ma_header = mo.md("## M-A Plot")
    else:
        ma_header = None

    ma_header
    return (ma_header,)


@app.cell
def _(df, min_lfc, mo, params, prepared_df, px):
    if df is not None:
        with mo.status.spinner("Making plot"):
            ma_fig = px.scatter(
                data_frame=prepared_df,
                x=params["lfc_cname"],
                y=params["abund_cname"],
                color="passes_threshold",
                labels={
                    "_neg_log10_pval": params["pval_label"],
                    params["lfc_cname"]: params["lfc_label"],
                    params["abund_cname"]: params["abund_label"],
                    "passes_threshold": "Passes Threshold",
                },
                hover_name=params["label_cname"],
                hover_data=[params["pval_cname"], params["abund_cname"]],
                log_y=params["abund_log"],
                template=params["theme"],
                width=params["width"],
                height=params["height"]
            )
            ma_fig.update_layout(
                plot_bgcolor="white",  # Set plot background color
                paper_bgcolor="white", # Set paper background color
                xaxis=dict(
                    showgrid=True,  # Show grid lines on the x-axis
                    gridcolor='lightgray'  # Set the color of the grid lines
                ),
                yaxis=dict(
                    showgrid=True,  # Show grid lines on the y-axis
                    gridcolor='lightgray'  # Set the color of the grid lines
                )
            )
            if min_lfc is not None:
                ma_fig.add_vline(min_lfc, line_dash="dash", line_color="grey", opacity=0.5)
                ma_fig.add_vline(-min_lfc, line_dash="dash", line_color="grey", opacity=0.5)

    else:
        ma_fig = None

    ma_fig
    return (ma_fig,)


@app.cell
def _(mo, three_dim_fig):
    if three_dim_fig is not None:
        three_dim_header = mo.md("## 3D Plot")
    else:
        three_dim_header = None

    three_dim_header
    return (three_dim_header,)


@app.cell
def _(df, mo, params, prepared_df, px):
    if df is not None:
        with mo.status.spinner("Making plot"):
            three_dim_fig = px.scatter_3d(
                data_frame=prepared_df,
                x=params["lfc_cname"],
                y="_neg_log10_pval",
                z=params["abund_cname"],
                color="passes_threshold",
                labels={
                    "_neg_log10_pval": params["pval_label"],
                    params["lfc_cname"]: params["lfc_label"],
                    params["abund_cname"]: params["abund_label"],
                    "passes_threshold": "Passes Threshold",
                },
                hover_name=params["label_cname"],
                hover_data=[params["pval_cname"], params["abund_cname"]],
                log_z=params["abund_log"],
                template=params["theme"],
                width=params["width"],
                height=params["height"]
            )

    else:
        three_dim_fig = None

    three_dim_fig
    return (three_dim_fig,)


@app.cell
def _(prepared_df):
    # Show the DataFrame with the rows passing the filter
    (
        prepared_df
        .query("passes_threshold")
        .drop(columns=[
            "passes_threshold",
            "_neg_log10_pval"
        ])
    )
    return


@app.cell
def _(mo, params, query_params, volcano_fig):
    if volcano_fig is not None:
        permalink = mo.md(
            (
                "[Permalink](https://fredhutch.github.io/differential-expression-viewer?{_query_params})"
                .format(
                    _query_params="&".join([
                        f"{kw}={str(val)}"
                        for kw, val in {
                            **{
                                kw: query_params.get(kw)
                                for kw in ["url", "domain", "project", "dataset", "file"]
                            },
                            **params
                        }.items()
                        if val is not None
                    ])
                )
            )
        )
    else:
        permalink = None
    permalink
    return (permalink,)


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
