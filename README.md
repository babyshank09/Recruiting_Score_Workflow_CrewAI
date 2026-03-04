# Recruiting Score Flow

Welcome to the Recruiting Score Flow project, powered by crewAI. This example demonstrates how you can leverage Flows from crewAI to automate the process of scoring candidates, including data collection, analysis, and scoring. By utilizing Flows, the process becomes much simpler and more efficient.


## Overview  

This flow will guide you through the process of setting up an automated lead scoring system. Here's a brief overview of what will happen in this flow:

**Load Candidates:** The flow starts by loading lead data from a CSV file named candidates.csv.

**Score Candidates:** The RecruitingScoreCrew is kicked off to score the loaded candidates based on predefined criteria.

**Human in the Loop:** The top 3 candidates are presented for human review, allowing for additional feedback or proceeding with writing emails.

**Write and Save Emails:** Emails are generated and saved for all candidates.

By following this flow, you can efficiently automate the process of scoring candidates, leveraging the power of multiple AI agents to handle different aspects of the lead scoring workflow.

## Running the Project

To get the project up and running on your local machine, follow these steps:

1. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```
2. Change into the `src` directory:
   ```bash
   cd src
   ```
3. Launch the Streamlit application:
   ```bash
   python -m streamlit run recruiter_score_flow/app.py
   ```

These commands will start the Streamlit UI where you can interact with the Recruiting Score Flow.
