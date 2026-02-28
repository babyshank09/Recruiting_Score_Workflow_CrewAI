from typing import List
import pandas as pd
from pathlib import Path 
import asyncio
import os 

from crewai.flow.flow import Flow, listen, or_, router, start
from pydantic import BaseModel, Field
from uuid import uuid4


from recruiter_score_flow.constants.constants import JOB_DESCRIPTION
from recruiter_score_flow.crews.recruiting_response_crew.recruiting_response_crew import RecruitingResponseCrew
from recruiter_score_flow.crews.recruiting_score_crew.recruiting_score_crew import RecruitingScoreCrew
from recruiter_score_flow.schema.schema import Candidate, CandidateScore, ScoredCandidate
from recruiter_score_flow.utils.candidate_utils import combine_candidates_with_scores 


class RecruitingScoreState(BaseModel): 
    id: str = Field(default_factory=lambda: str(uuid4()))
    candidates: List[Candidate] = []
    candidate_score : List[CandidateScore] = []
    hydrated_candidates : List[ScoredCandidate] = [] 
    scoring_feedback : str = " " 


class RecruitingScoreFlow(Flow[RecruitingScoreState]):  
    initial_state = RecruitingScoreState 

    @start() 
    def load_candidates(self):  
        current_dir = Path(__file__).parent 
        csv_filepath = current_dir / "database/candidates.csv" 
        candidates = [] 

        df = pd.read_csv(csv_filepath) 
        for row in df.to_dict(orient="records"):
            print("LOADING CANDIDATE:", row)
            row["id"] = str(row["id"])
            candidate = Candidate(**row) 
            candidates.append(candidate)
        
        self.state.candidates = candidates 
    
    
    @listen(or_(load_candidates, "scored_candidates_feedback"))
    async def score_candidates(self):  
        print("Scoring Candidates...") 
        tasks = [] 

        async def score_single_candidate(candidate: Candidate): 
            print("Scoring Candidate:", candidate) 
            result = await RecruitingScoreCrew().crew().kickoff_async(
                inputs = {
                    "candidate_id": candidate.id, 
                    "name": candidate.name, 
                    "bio": candidate.bio, 
                    "job_description": JOB_DESCRIPTION, 
                    "additional_instructions": self.state.scoring_feedback
                }
            )
            self.state.candidate_score.append(result.pydantic) 
        
        for candidate in self.state.candidates: 
            print("Scoring candidate:", candidate.name)  
            task = asyncio.create_task(score_single_candidate(candidate)) 
            tasks.append(task) 

        candidate_scores = await asyncio.gather(*tasks) 
        print(f"Finished scoring {len(candidate_scores)} candidates") 


    @router(score_candidates) 
    def human_in_the_loop(self):
        print("Finding the top 3 candidates for human to review")  

        self.state.hydrated_candidates = combine_candidates_with_scores(self.state.candidates, self.state.candidate_score) 
        sorted_candidates = sorted(self.state.hydrated_candidates, key= lambda c: c.score, reverse=True) 
        top_3_candidates = sorted_candidates[:3] 

        print("\n")
        print("#####################################################################")
        print("** Human in the Loop **")

        print("Here are the top 3 candidates:")
        for candidate in top_3_candidates:
            print(
                f"ID: {candidate.id}, Name: {candidate.name}, Score: {candidate.score}, Reason: {candidate.reason}\n"
            ) 

        print("\nPlease choose an option:")
        print("1. Quit")
        print("2. Redo lead scoring with additional feedback")
        print("3. Proceed with writing emails to all leads")

        choice = input("Enter the number of your choice: ")

        if choice == "1":
            print("Exiting the program.")
            exit()

        elif choice == "2":
            feedback = input(
                "\nPlease provide additional feedback on what you're looking for in candidates:\n"
            )
            self.state.scoring_feedback = feedback
            print("\nRe-running lead scoring with your feedback...")
            return "scored_candidates_feedback"
        
        elif choice == "3":
            print("\nProceeding to write emails to all leads.") 
            output_dir = Path(__file__).parent / "output/selected_candidates"
            os.makedirs(output_dir, exist_ok=True) 
            
            for candidate in top_3_candidates: 
                data = f"ID: {candidate.id}\nName: {candidate.name}\nEmail: {candidate.email}\nBio: {candidate.bio}\nSkills: {candidate.skills}\nScore: {candidate.score}\nReason: {candidate.reason}"
                with open(output_dir / f"{candidate.name}.txt", "w") as f:
                    f.write(data)
            return "generate_emails"
        
        else:
            print("\nInvalid choice. Please try again.")
            return "human_in_the_loop"
        

    @listen("generate_emails")
    async def write_and_save_emails(self):
        import re
        from pathlib import Path

        print("Writing and saving emails for all leads.")

        top_candidate_ids = {
            candidate.id for candidate in self.state.hydrated_candidates[:3]
        }

        tasks = []

        output_dir = Path(__file__).parent / "output/email_responses"
        print("output_dir:", output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        async def write_email(candidate):
            proceed_with_candidate = candidate.id in top_candidate_ids

            result = await (
                RecruitingResponseCrew()
                .crew()
                .kickoff_async(
                    inputs={
                        "candidate_id": candidate.id,
                        "name": candidate.name,
                        "bio": candidate.bio,
                        "proceed_with_candidate": proceed_with_candidate,
                    }
                )
            )

            safe_name = re.sub(r"[^a-zA-Z0-9_\- ]", "", candidate.name)
            filename = f"{safe_name}.txt"
            print("Filename:", filename)

            file_path = output_dir / filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(result.raw)

            return f"Email saved for {candidate.name} as {filename}"

        for candidate in self.state.hydrated_candidates:
            task = asyncio.create_task(write_email(candidate))
            tasks.append(task)

        email_results = await asyncio.gather(*tasks)

        print("\nAll emails have been written and saved to 'email_responses' folder.")
    


def kickoff():
    """
    Run the flow.
    """
    recruiting_score_flow = RecruitingScoreFlow()
    recruiting_score_flow.kickoff()


def plot():
    """
    Plot the flow.
    """
    recruiting_score_flow = RecruitingScoreFlow()
    recruiting_score_flow.plot()


if __name__ == "__main__":
    kickoff() 
    # plot()









            



        






