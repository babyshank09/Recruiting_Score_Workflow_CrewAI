import pandas as pd 
from typing import List 
from recruiter_score_flow.schema.schema import CandidateScore, Candidate, ScoredCandidate 

def combine_candidates_with_scores(candidates: List[Candidate], candidate_scores: List[CandidateScore]) -> List[ScoredCandidate]: 
    
    print("COMBINING CANDIDATES WITH SCORES")
    # print("SCORES:", candidate_scores)
    # print("CANDIDATES:", candidates)
     
    scored_dict = {score.id : score for score in candidate_scores} 
    
    scored_candidates = [] 
    for candidate in candidates: 
        score = scored_dict.get(candidate.id) 
        if score is not None: 
            scored_candidates.append(
                ScoredCandidate(
                    id = candidate.id, 
                    name = candidate.name, 
                    email = candidate.email, 
                    bio = candidate.bio, 
                    skills = candidate.skills, 
                    score = score.score, 
                    reason = score.reason
                )
            ) 
    
    # print("SCORED CANDIDATES:", scored_candidates) 
    rows = []

    for scored_candidate in scored_candidates:
        rows.append({
            "id": scored_candidate.id,
            "name": scored_candidate.name,
            "email": scored_candidate.email,
            "bio": scored_candidate.bio,
            "skills": scored_candidate.skills,
            "score": scored_candidate.score,
            "reason": scored_candidate.reason
        })
    df = pd.DataFrame(rows)

    df.to_csv("recruiter_score_flow/output/scored_candidates.csv", index=False) 
    return scored_candidates
    
    





