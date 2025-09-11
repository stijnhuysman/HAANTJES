"""

Extract player information from TEGENPLOEG.HTML

This script specifically extracts player information from the TEGENPLOEG.HTML file,
focusing on the opponent team's players (Tuit section).
"""

import os
from bs4 import BeautifulSoup
import pandas as pd
import re

# Path to the HTML file
html_file_path = "TEGENPLOEG.HTML"

def extract_opponent_players(html_path):
    """Extract opponent team player information from the HTML file"""
    print(f"Reading HTML file: {html_path}")
    
    # Check if file exists
    if not os.path.exists(html_path):
        print(f"Error: File {html_path} does not exist")
        return None
    
    # Read the HTML file
    with open(html_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    print(f"HTML file read successfully: {len(html_content)} characters")
    
    # Parse HTML using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the section with opponent players - usually in the sectionDweg div with TU content
    players_section = soup.find('div', id='sectionDweg')
    
    if not players_section:
        print("Could not find the opponent players section (sectionDweg)")
        return None
    
    # Find tbody within the player section table
    tbody = players_section.find('tbody')
    
    if not tbody:
        print("Could not find tbody element in the opponent players section")
        return None
    
    print("Found opponent players section and tbody element")
    
    # Extract player information
    player_data = []
    
    # Find rows with player data - they usually have the ng-repeat attribute with "deelnemer in Tuit"
    player_rows = tbody.find_all('tr', attrs={"ng-repeat": lambda value: value and "deelnemer in Tuit" in value})
    
    for row in player_rows:
        td_elements = row.find_all('td')
        
        # Skip rows with insufficient data
        if len(td_elements) < 5:
            continue
        
        # Extract player name (usually in 5th column)
        player_name_td = td_elements[4] if len(td_elements) > 4 else None
        if not player_name_td:
            continue
            
        player_name = player_name_td.get_text().strip()
        
        # Skip coaches and delegates
        if any(role in player_name.lower() for role in ["coach", "ass.", "delegate", "gedelegeerde"]):
            continue
        
        # Extract jersey number if available (usually in 4th column with a format like "13 ")
        jersey_number_td = td_elements[3] if len(td_elements) > 3 else None
        jersey_number = ""
        if jersey_number_td:
            # Extract number from text like "13 (J16)"
            number_text = jersey_number_td.get_text().strip()
            number_match = re.search(r'(\d+)', number_text)
            if number_match:
                jersey_number = number_match.group(1)
        
        # Add player info to the list
        player_data.append({
            "jersey_number": jersey_number,
            "player_name": player_name,
        })
    
    print(f"Extracted information for {len(player_data)} players")
    return player_data

def save_opponent_data(player_data):
    """Save the extracted player data to CSV and display it"""
    if not player_data:
        print("No player data to save")
        return
    
    # Create DataFrame from player data
    df = pd.DataFrame(player_data)
    
    # Save to CSV
    csv_filename = "opponent_players.csv"
    df.to_csv(csv_filename, index=False)
    print(f"Saved player data to {csv_filename}")
    
    # Display the data
    print("\nOpponent Team Players:")
    print(df)

def main():
    # Extract player data from the opponent section
    player_data = extract_opponent_players(html_file_path)
    
    # Save and display the data
    save_opponent_data(player_data)

if __name__ == "__main__":
    main()
