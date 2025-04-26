import logging
import httpx
from typing import Optional, Dict, Any, Literal

from pydantic import Field, ValidationError
from fastapi import HTTPException, status
from pydantic_ai import RunContext

from app.backend.agent.agent import AgentDependencies


logger = logging.getLogger(__name__)


type AllowedCategories = Literal["business", "entertainment", "general", "health", "science", "sports", "technology"]

async def get_weather(
    ctx: RunContext[AgentDependencies],
    city: str,
    country_code: Optional[str] = None,
) -> str:
    """
    Fetches the current weather for a specified city using OpenWeatherMap API
    and returns a formatted string summary.

    Args:
        ctx: RunContext containing dependencies and information about the current call.
        city: The name of the city to fetch weather for.
        country_code: Optional 2-letter country code (ISO 3166) for the city.
    Returns:
        A formatted string summarizing the current weather.
    """
    if not ctx.deps.settings.OPENWEATHER_API_KEY:
        logger.error("OpenWeatherMap API key not configured.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Weather service key not configured.")

    api_key = ctx.deps.settings.OPENWEATHER_API_KEY.get_secret_value()
    weather_url = "https://api.openweathermap.org/data/2.5/weather"

    query_param = f"{city},{country_code}" if country_code else city
    params = {
        "q": query_param,
        "appid": api_key,
        "units": "metric"
    }

    logger.info(f"Fetching weather for: {query_param}")

    try:
        response = await ctx.deps.session.get(url=weather_url, params=params)
        response.raise_for_status()
        data = response.json()

        location=f"{data['name']}, {data['sys']['country']}"
        temp=data['main']['temp']
        feels_like=data['main']['feels_like']
        description=data['weather'][0]['description']
        humidity=data['main']['humidity']
        wind_speed=data['wind']['speed']

        result_string = (
            f"Current weather in {location}:\n"
            f"- Condition: {description.capitalize()}\n"
            f"- Temperature: {temp:.1f}°C (Feels like: {feels_like:.1f}°C)\n"
            f"- Humidity: {humidity}%\n"
            f"- Wind Speed: {wind_speed:.2f} m/s"
        )


        logger.info(f"Weather fetched successfully for {location}")
        return result_string
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"City not found for weather: {query_param}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"City '{query_param}' not found.")
        elif e.response.status_code == 401:
            logger.error("OpenWeatherMap API key invalid or missing.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Weather service authentication failed.")
        else:
            logger.error(f"HTTP error fetching weather for {query_param}: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Weather service unavailable.")
    except (httpx.RequestError, ValidationError, KeyError, IndexError) as e:
        logger.error(f"Error processing weather data for {query_param}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not process weather data: {e}")


async def get_latest_news(
    ctx: RunContext[AgentDependencies],
    country: str,
    query: Optional[str] = None,
    category: Optional[AllowedCategories] = None,
) -> str:
    """
    Fetches the latest news articles from NewsAPI based on the provided parameters.
    Args:
        ctx: RunContext containing dependencies and information about the current call.
        query: Optional keywords or phrase to search for in news articles.
        country: The 2-letter ISO 3166-1 code of the country (e.g., us, gb, de).
        category: Optional category (e.g., business, technology, sports).

    Returns:
        A formatted string summarizing the latest news articles.
    """
    if not ctx.deps.settings.NEWS_API_KEY:
        logger.error("NewsAPI API key not configured.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="News service key not configured.")
    
    api_key = ctx.deps.settings.NEWS_API_KEY.get_secret_value()
    news_url = "https://newsapi.org/v2/top-headlines"

    params: Dict[str, Any] = {
    "country": country,
    "apiKey": api_key,
    "pageSize": 3
}
    request_description = f"top headlines for country '{country}'"
    if query:
        params["q"] = query
        request_description += f" matching query '{query}'"
    if category:
        params["category"] = category.lower()
        request_description += f" in category '{category.lower()}'"

    logger.info(f"Fetching news with params: {params}")
    try:
        response = await ctx.deps.session.get(url=news_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "ok":
            logger.error(f"NewsAPI error: Code={data.get('code')}, Message={data.get('message')}")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"News service error: {data.get('message', 'Unknown error')}")
        articles_data = data.get("articles", [])
        if not articles_data:
            return f"No news articles found for {request_description}."
        result_lines = [f"Found {len(articles_data)} news articles ({request_description}):"]
        for i, article in enumerate(articles_data):
            title = article.get("title", "No Title")
            source = article.get("source", {}).get("name", "Unknown Source")
            desc = article.get("description", "No description available.")
            url = article.get("url")
            if url:
                result_lines.append(f"{i+1}. \"{title}\" ({source})\n   Desc: {desc}\n   URL: {url}")
        result_string = "\n".join(result_lines)

        logger.info(f"News fetched successfully. Articles returned: {len(articles_data)}")
        return result_string
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
             logger.error("NewsAPI API key invalid or missing.")
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="News service authentication failed.")
        elif e.response.status_code == 429:
             logger.warning("NewsAPI rate limit hit.")
             raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="News service rate limit exceeded.")
        else:
             logger.error(f"HTTP error fetching news: {e.response.status_code} - {e.response.text}")
             raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="News service unavailable.")
    except (httpx.RequestError, ValidationError, KeyError, IndexError) as e:
        logger.error(f"Error processing news data: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Could not process news data: {e}")