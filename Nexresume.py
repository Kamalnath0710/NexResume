import os
import json
import yaml
import PyPDF2
from openai import OpenAI
from dotenv import load_dotenv

def load_job_description(filepath="job_description.yml"):
    """Loads the job description from a YAML file."""
    with open(filepath, 'r') as file:
        return yaml.safe_load(file)
    
def extract_text_from_resume(filepath):
    """Extracts text from a resume file (PDF or TXT)."""
    text = ""
    if filepath.endswith('.pdf'):
        with open(filepath, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""
    elif filepath.endswith('.txt'):
        with open(filepath, 'r') as file:
            text = file.read()
    return text

def create_llm_prompt(job_desc, resume_text):
    # The required JSON structure for the LLM's response 
    json_format_instructions = """
    {
        "matched_required_skills": [],
        "missing_required_skills": [],
        "matched_optional_skills": [],
        "education_match": "Yes/No/Partial",
        "experience_match": "Yes/No",
        "keywords_matched": [],
        "soft_skills_match": "A brief analysis of soft skills match.",
        "resume_summary": "A 2-3 sentence summary of the resume.",
        "match_score": 0.0,
        "city_tier_match": "Yes/No/Not Applicable",
        "longest_tenure_months": 0,
        "final_score": 0
    }
    """

    prompt = f"""
    Analyze the following resume against the provided job description for an IT role in India. 
    Your task is to act as an expert IT recruiter and return a JSON object with a detailed analysis.

    EVALUATION CRITERIA (IMPORTANT):
    1.  Semantic Matching : Do not just keyword match. Understand the context. For example, if the resume lists "API development" and the job requires "REST APIs", that's a strong match.
    2.  Scoring Logic for 'final_score' (0-100 integer):
        * The 'final_score' must summarize the overall quality.
        * **Stability Bonus**: Candidates with a longer tenure in a single job ('longest_tenure_months') are more stable and should receive a higher score. 
        * **Geographic Diversity Bonus**: Candidates from Tier-3 cities are highly valued to promote diversity. If the candidate's location appears to be in a Tier-3 city (any city not in Tier-1 or Tier-2 lists), give them a significant bonus in the score.
    3.  City Tier Logic: Based on the candidate's most recent location in the resume, determine if their city tier matches the tier specified in the job description ('{job_desc.get('City_Tier')}'). 
        * Tier-1 Cities: {job_desc.get('Tier-1_cities')} 
        * Tier-2 Cities (Examples): {job_desc.get('Tier-2_cities')} 
        * Tier-3 Cities: All other cities. 

    **JOB DESCRIPTION:**
    ```json
    {json.dumps(job_desc, indent=2)}
    ```

    **RESUME TEXT:**
    ```
    {resume_text}
    ```

    **YOUR RESPONSE (must be ONLY the JSON object below):**
    Return a single, valid JSON object structured exactly as follows:
    ```json
    {json_format_instructions}
    ```
    """
    return prompt   

def get_analysis_from_gpt(prompt):
    """Sends the prompt to the GPT API and gets the structured response."""
    load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} # Ensures the output is a JSON object
        )
        # The API returns a JSON string, so we parse it into a Python dict
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"An error occurred with the API call: {e}")
        return None 
    
def process_resumes_in_batch(job_desc, resumes_folder="resumes/", reports_folder="reports/"):
    """Processes all resumes in a folder and saves the reports."""
    if not os.path.exists(reports_folder):
        os.makedirs(reports_folder) # Create reports folder if it doesn't exist 
        
    # Iterate through all files in the resumes folder 
    for filename in os.listdir(resumes_folder):
        # Process only .pdf and .txt files 
        if filename.endswith(('.pdf', '.txt')):
            print(f"Processing {filename}...")
            filepath = os.path.join(resumes_folder, filename)
            
            try:
                resume_text = extract_text_from_resume(filepath)
                
                # Handle cases of empty or unreadable resumes 
                if not resume_text or resume_text.isspace():
                    print(f"Could not extract text from {filename}. Skipping.")
                    continue
                
                # Construct the prompt and get analysis
                prompt = create_llm_prompt(job_desc, resume_text)
                analysis_result = get_analysis_from_gpt(prompt)
                
                # Save the report if the analysis was successful 
                if analysis_result:
                    # Add candidate name to the report 
            
                    analysis_result['candidate_name'] = os.path.splitext(filename)[0]
                    
                    report_filename = f"{os.path.splitext(filename)[0]}_report.json"
                    report_filepath = os.path.join(reports_folder, report_filename)
                    
                    with open(report_filepath, 'w') as report_file:
                        json.dump(analysis_result, report_file, indent=4)
                    print(f"Successfully generated report for {filename}")
                else:
                    print(f"Failed to get analysis for {filename}.")
            
            except Exception as e:
                # This ensures the system doesn't crash on a single bad file 
                print(f"An error occurred while processing {filename}: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("Starting NexResume Semantic Matcher...")
    job_description = load_job_description()
    
    # We add the city tier info from the document directly to the job_description dict
    # This makes it available to the prompt.
    job_description['Tier-1_cities'] = ["Chennai", "Bangalore", "Delhi", "Hyderabad", "Kolkata", "Mumbai"] 
    job_description['Tier-2_cities'] = ["Coimbatore", "Trichy", "Madurai"] 

    process_resumes_in_batch(job_description)
    print("Processing complete. Reports are saved in the 'reports/' folder.")    