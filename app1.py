import streamlit as st
import os
from huggingface_hub import InferenceClient
import requests
import ast
import re
from PIL import Image
from io import BytesIO
import time

# Constants
HF_API_KEY = "your_huggingface_api_key"
STABLE_DIFFUSION_URL = "https://api-inference.huggingface.co/models/CompVis/stable-diffusion-v1-4"
SPOONACULAR_API_KEY = 'your_spoonacular_api_key'
ACCESS_TOKEN = "your_instagram_access_token"
INSTAGRAM_ACCOUNT_ID = "your_instagram_account_id"
IMGUR_CLIENT_ID = "your_imgur_client_id"

client = InferenceClient(api_key=HF_API_KEY)

# Function to generate anime-inspired dish
def generate_anime_inspired_dish(anime_name, dish_type ,model="mistralai/Mistral-7B-Instruct-v0.2"):
    message = {
        "role": "user",
        "content": f"Create a unique food dish inspired by the anime '{anime_name}'." 
                   f"It should be a '{dish_type}' dish. "
                   "Include the following details in a clear enumeration structure: "
                   "1. **Dish Name**: Provide a catchy name for the dish. "
                   "2. **Ingredients**: List all key ingredients with specific quantities in grams and only in grams. "
                   "3. **Preparation Steps**: Outline the cooking process in concise steps. "
                   "4. **Cultural Significance**: Explain how the dish reflects the themes or characters of the anime, "
                   "highlighting any specific scenes or elements that inspired it. "
                   "Ensure the description is no longer than 500 characters."
    }
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[message],
            max_tokens=500,
            stream=False
        )
        result = response["choices"][0].get("message", {}).get("content", "No content generated.")
        return result
    except Exception as e:
        st.error(f"Error generating dish: {e}")
        return None

def extract_and_replace_ingredients(food_description):
    messages = [
        {
            "role": "user",
            "content": f"From the following dish description: '{food_description}', "
                       "extract a list of real-life ingredients along with their quantities. "
                       "If any ingredient is fictional or not readily available, replace it with a real-life equivalent that closely matches its characteristics or purpose. "
                       "Use general terms as fallbacks for specific ingredients, ensuring they are realistic and usable in cooking. "
                       "Return the final ingredients as a Python dictionary where the key is the ingredient name and the value is the quantity. "
                       "Ensure the output is formatted as a dictionary with proper key-value pairs."
                }
    ]
    try:
        response = client.chat.completions.create(
            model="mistralai/Mistral-7B-Instruct-v0.2",
            messages=messages,
            max_tokens=500,
            stream=False
        )
        ingredients_dict_str = response["choices"][0]["message"]["content"].strip()
        match = re.search(r'\{.*\}', ingredients_dict_str, re.DOTALL)
        if match:
            cleaned_dict_str = match.group(0)
            cleaned_dict_str = cleaned_dict_str.replace("’", "'")
            try:
                # Use ast.literal_eval safely to evaluate dictionary string
                ingredients_dict = ast.literal_eval(cleaned_dict_str)
                return ingredients_dict
            except (SyntaxError, ValueError) as eval_error:
                st.error(f"Error evaluating the dictionary: {eval_error}")
                return None
        else:
            st.error("No valid dictionary found in the response.")
            return None
    except Exception as e:
        st.error(f"Error extracting ingredients: {e}")
        return None

def clean_ingredients(ingredients_dict):
    cleaned_dict = {}
    for ingredient, quantity in ingredients_dict.items():
        cleaned_ingredient = ingredient.split('(')[0].strip()
        cleaned_ingredient = re.sub(r'\s+', ' ', cleaned_ingredient).strip()
        cleaned_dict[cleaned_ingredient] = quantity.strip()
    print(cleaned_dict)
    return cleaned_dict

def extract_quantity(quantity_str):
    try:
        if "/" in quantity_str:
            numerator, denominator = quantity_str.split("/")
            return float(numerator) / float(denominator)
        else:
            return float(''.join(filter(str.isdigit, quantity_str)))
    except ValueError:
        return 0.0

def get_ingredient_id(ingredient_name):
    url = "https://api.spoonacular.com/food/ingredients/search"
    params = {'query': ingredient_name, 'apiKey': SPOONACULAR_API_KEY}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if 'results' in data and data['results']:
            return data['results'][0]['id']
        else:
            print(f"No results for '{ingredient_name}'. Trying simpler version...")
            simplified_name = ingredient_name.split()[0]
            return get_ingredient_id(simplified_name)
    except Exception as e:
        st.error(f"Error fetching ID for {ingredient_name}: {e}")
        return None

def get_nutritional_info(ingredient_id, quantity, unit="g"):
    url = f"https://api.spoonacular.com/food/ingredients/{ingredient_id}/information"
    params = {'amount': quantity, 'unit': unit, 'apiKey': SPOONACULAR_API_KEY}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching nutritional info for {ingredient_id}: {e}")
        return {}

def create_image_prompt(dish_description):
    if not dish_description or not isinstance(dish_description, str):
        raise ValueError("Dish description must be a non-empty string.")
    return (
        f"Create a visually stunning and appetizing image based on the following dish description: {dish_description}. "
        f"Use vibrant colors, anime-style aesthetics, and include elements that reflect the cultural significance of the dish. "
        f"Present the dish in an artistic way, with a decorative background that enhances its appeal. "
        f"Make it Instagram-worthy with emphasis on details and presentation."
    )

def generate_image_from_description(description, retries=3, delay=5):
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"inputs": description}
    
    for attempt in range(retries):
        try:
            response = requests.post(STABLE_DIFFUSION_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()

            if response.content:
                image = Image.open(BytesIO(response.content))
                image_path = "generated_image.png"
                image.save(image_path)
                print("Image generated successfully.")
                return image_path
            else:
                print("No image data returned.")
        except requests.exceptions.Timeout:
            print("Request timed out. Retrying...")
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}. Retrying...")
        except Exception as e:
            print(f"Unexpected error: {e}.")
        
        time.sleep(delay)
    else:
        print(f"Failed to generate image after {retries} attempts.")
        return None

def upload_image_to_imgur(image_path):
    headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
    with open(image_path, "rb") as image_file:
        files = {"image": image_file}
        response = requests.post("https://api.imgur.com/3/image", headers=headers, files=files)
        
    if response.status_code == 200:
        image_url = response.json()["data"]["link"]
        print(f"Image uploaded to Imgur. URL: {image_url}")
        return image_url
    else:
        print(f"Error uploading to Imgur: {response.text}")
        return None

def upload_image_to_instagram(image_url, caption):
    url = f"https://graph.facebook.com/v14.0/{INSTAGRAM_ACCOUNT_ID}/media"
    payload = {
        'image_url': image_url,
        'caption': caption,
        'access_token': ACCESS_TOKEN
    }

    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        media_id = response.json().get("id")
        print(f"Image uploaded successfully. Media ID: {media_id}")
        
        publish_url = f"https://graph.facebook.com/v14.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
        publish_payload = {
            'creation_id': media_id,
            'access_token': ACCESS_TOKEN
        }
        
        publish_response = requests.post(publish_url, data=publish_payload)
        
        if publish_response.status_code == 200:
            print("Image published successfully to Instagram!")
            return True, "Image published successfully to Instagram!"
        else:
            error_message = publish_response.json().get('error', {}).get('message', 'Unknown error')
            print(f"Error publishing image: {publish_response.text}")
            return False, f"Error publishing image: {error_message}"
    else:
        error_message = response.json().get('error', {}).get('message', 'Unknown error')
        print(f"Error uploading image: {response.text}")
        return False, f"Error uploading image: {error_message}"

def calculate_nutritional_info(cleaned_ingredients):
    total_protein = total_carbohydrates = total_fat = total_calories = 0.0
    for ingredient, quantity in cleaned_ingredients.items():
        numeric_quantity = extract_quantity(quantity)
        unit = "g" if "g" in quantity else ("ml" if "ml" in quantity else "unit")
        ingredient_id = get_ingredient_id(ingredient)
        if ingredient_id:
            nutrition_info = get_nutritional_info(ingredient_id, numeric_quantity, unit)
            nutrients = nutrition_info.get('nutrition', {}).get('nutrients', [])
            protein = next((n['amount'] for n in nutrients if n['name'] == 'Protein'), 0.0)
            carbs = next((n['amount'] for n in nutrients if n['name'] == 'Carbohydrates'), 0.0)
            fats = next((n['amount'] for n in nutrients if n['name'] == 'Fat'), 0.0)
            calories = next((n['amount'] for n in nutrients if n['name'] == 'Calories'), 0.0)
            total_protein += protein
            total_carbohydrates += carbs
            total_fat += fats
            total_calories += calories
    total_nutritional_value = {
        'Total Protein (g)': total_protein,
        'Total Carbohydrates (g)': total_carbohydrates,
        'Total Fat (g)': total_fat,
        'Total Calories (kcal)': total_calories
    }
    return total_nutritional_value

def apply_custom_css():
    st.markdown("""
    <style>
    /* Customize main area */
    .main {
        background-color: #f0f0f5;
    }
    /* Customize titles and headers */
    .stMarkdown h1 {
        color: #ff4b4b;
    }
    .stMarkdown h2 {
        color: #ff4b4b;
    }
    /* Customize buttons */
    .stButton>button {
        background-color: #ff4b4b;
        color: white;
        border-radius: 5px;
        height: 50px;
        width: 100%;
        font-size: 18px;
    }
    /* Sidebar styling */
    .sidebar .sidebar-content {
        background-image: linear-gradient(#ff7f50,#ff6347);
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

def display_results(dish_description, anime_name):
    st.session_state['dish_description'] = dish_description
    st.session_state['anime_name'] = anime_name

    st.markdown(f"## 🍜 Dish Inspired by **{anime_name}**")
    st.write(dish_description)

    # Create columns for layout
    col1, col2 = st.columns(2)

    # Extract and display ingredients
    with col1:
        ingredients_dict = extract_and_replace_ingredients(dish_description)
        if ingredients_dict:
            cleaned_ingredients = clean_ingredients(ingredients_dict)
            st.session_state['cleaned_ingredients'] = cleaned_ingredients
            st.subheader("📝 Ingredients")
            st.write(cleaned_ingredients)
        else:
            st.error("Failed to extract ingredients.")

    # Generate and display image
    with col2:
        image_prompt = create_image_prompt(dish_description)
        image_path = generate_image_from_description(image_prompt)
        if image_path:
            st.session_state['image_path'] = image_path
            st.image(image_path, caption="Generated Image")
        else:
            st.error("Failed to generate image.")

    # Display nutritional information
    total_nutritional_value = calculate_nutritional_info(st.session_state['cleaned_ingredients'])
    st.session_state['total_nutritional_value'] = total_nutritional_value
    with st.expander("📊 Nutritional Information"):
        st.write(total_nutritional_value)

    # Option to share on Instagram
    if st.button("Share on Instagram"):
        if 'image_path' in st.session_state and st.session_state['image_path']:
            image_url = upload_image_to_imgur(st.session_state['image_path'])
            caption = f"Check out this delicious anime-inspired dish! 🍜✨ #AnimeFood #FoodArt\n\n{st.session_state['dish_description']}\n\nNutritional Information:\n{st.session_state['total_nutritional_value']}"
            success, message = upload_image_to_instagram(image_url, caption)
            if success:
                st.success("Shared on Instagram!")
            else:
                st.error(f"Failed to share on Instagram: {message}")
        else:
            st.error("No image available to share.")

def main():
    # Apply custom CSS
    apply_custom_css()

    # Sidebar
    st.sidebar.title("🍣 Anime-Inspired Dish Generator")
    anime_name = st.sidebar.text_input("Enter an Anime Name", "Bleach")
    dish_type = st.sidebar.text_input("Enter a Dish Type", "Cake")
    generate_button = st.sidebar.button("Generate Dish")
    # Main content
    st.title("🍱 Welcome to the Anime-Inspired Dish Generator!")
    st.write("Experience a fusion of culinary arts and anime creativity.")

    if generate_button:
        with st.spinner('Generating your unique dish...'):
            dish_description = generate_anime_inspired_dish(anime_name, dish_type)
        if dish_description:
            st.session_state['anime_name'] = anime_name
            st.session_state['dish_description'] = dish_description
            display_results(dish_description, anime_name)
        else:
            st.error("Failed to generate dish description.")
    elif 'dish_description' in st.session_state:
        display_results(st.session_state['dish_description'], st.session_state['anime_name'])

if __name__ == "__main__":
    main()