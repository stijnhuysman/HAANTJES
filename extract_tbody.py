"""

Extract <tbody> content from TEGENPLOEG.HTML

This script reads the HTML content from TEGENPLOEG.HTML and extracts 
all <tbody> elements, saving each one to a separate file.
"""

import os
from bs4 import BeautifulSoup
import pandas as pd
import re

# Path to the HTML file
html_file_path = "TEGENPLOEG.HTML"

def extract_tbody_elements(html_path):
    """Extract all tbody elements from an HTML file"""
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
    
    # Find all tbody elements
    tbody_elements = soup.find_all('tbody')
    
    print(f"Found {len(tbody_elements)} tbody elements")
    
    return tbody_elements

def save_tbody_to_files(tbody_elements):
    """Save each tbody element to a separate file"""
    for i, tbody in enumerate(tbody_elements):
        # Create output filename
        output_filename = f"tbody_{i+1}.html"
        
        # Save the tbody content to file
        with open(output_filename, 'w', encoding='utf-8') as file:
            file.write(str(tbody.prettify()))
        
        print(f"Saved tbody #{i+1} to {output_filename}")

def extract_player_data(tbody_elements):
    """Extract player data from tbody elements that contain player information"""
    all_players = []
    
    for i, tbody in enumerate(tbody_elements):
        # Look for rows with player information
        rows = tbody.find_all('tr', class_='ng-scope')
        
        for row in rows:
            # Try to extract player name - typically in the 5th td element
            player_name_td = None
            td_elements = row.find_all('td')
            
            # Check for player name in different positions (layouts vary)
            if len(td_elements) >= 5:
                player_name_td = td_elements[4]  # Common position for player names
            elif len(td_elements) >= 3:
                player_name_td = td_elements[2]  # Alternative position
            
            if player_name_td and player_name_td.get_text().strip():
                player_name = player_name_td.get_text().strip()
                
                # Check if this is likely a player (not a coach or other role)
                if player_name and not any(role in player_name.lower() for role in ["coach", "ass.", "delegate", "gedelegeerde"]):
                    # Try to find the player's number, often in first column
                    player_number = ""
                    if td_elements and td_elements[0].get_text().strip():
                        player_number = td_elements[0].get_text().strip()
                    
                    all_players.append({
                        "tbody_index": i+1,
                        "player_number": player_number,
                        "player_name": player_name
                    })
    
    return all_players

def main():
    # Extract all tbody elements
    tbody_elements = extract_tbody_elements(html_file_path)
    if not tbody_elements:
        return
    
    # Save all tbody elements to files
    save_tbody_to_files(tbody_elements)
    
    # Extract player data 
    players = extract_player_data(tbody_elements)
    
    # Save player data to CSV
    if players:
        df = pd.DataFrame(players)
        df.to_csv("players.csv", index=False)
        print(f"Extracted {len(players)} players and saved to players.csv")
        
        # Display the player data
        print("\nExtracted Player Data:")
        print(df)
    else:
        print("No player data found")

if __name__ == "__main__":
    main()
