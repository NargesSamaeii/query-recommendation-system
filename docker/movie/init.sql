-- Loads netflix_dataset/*.csv into postgres-movie, with column names/types matching the CSV
-- headers verbatim so netfilx_sparql/netflix_ontology.obda's SELECTs work unmodified.
-- Runs automatically on first container start via docker-entrypoint-initdb.d.
--
-- NOTE: no PRIMARY KEY constraints here on purpose. This dataset intentionally injects
-- duplicate rows (README: "Duplicates (3-6% per table)") including duplicate id columns
-- (verified: 40/1040 movie_id, 300/10300 user_id, 5000/105000 session_id, 1500/26500
-- search_id, 450/15450 review_id, 2000/52000 recommendation_id) -- a PRIMARY KEY would abort
-- the bulk load. Plain (non-unique) indexes are added instead for join/lookup performance.

CREATE TABLE movies (
    movie_id text,
    title text,
    content_type text,
    genre_primary text,
    genre_secondary text,
    release_year integer,
    duration_minutes numeric,
    rating text,
    language text,
    country_of_origin text,
    imdb_rating numeric,
    production_budget numeric,
    box_office_revenue numeric,
    number_of_seasons numeric,
    number_of_episodes numeric,
    is_netflix_original boolean,
    added_to_platform date,
    content_warning boolean
);

CREATE TABLE users (
    user_id text,
    email text,
    first_name text,
    last_name text,
    age numeric,
    gender text,
    country text,
    state_province text,
    city text,
    subscription_plan text,
    subscription_start_date date,
    is_active boolean,
    monthly_spend numeric,
    primary_device text,
    household_size numeric,
    created_at timestamp
);

CREATE TABLE watch_history (
    session_id text,
    user_id text,
    movie_id text,
    watch_date date,
    device_type text,
    watch_duration_minutes numeric,
    progress_percentage numeric,
    action text,
    quality text,
    location_country text,
    is_download boolean,
    user_rating numeric
);

CREATE TABLE search_logs (
    search_id text,
    user_id text,
    search_query text,
    search_date date,
    results_returned integer,
    clicked_result_position integer,
    device_type text,
    search_duration_seconds numeric,
    had_typo boolean,
    used_filters boolean,
    location_country text
);

CREATE TABLE reviews (
    review_id text,
    user_id text,
    movie_id text,
    rating numeric,
    review_date date,
    device_type text,
    is_verified_watch boolean,
    helpful_votes numeric,
    total_votes numeric,
    review_text text,
    sentiment text,
    sentiment_score numeric
);

CREATE TABLE recommendation_logs (
    recommendation_id text,
    user_id text,
    movie_id text,
    recommendation_date date,
    recommendation_type text,
    recommendation_score numeric,
    was_clicked boolean,
    position_in_list integer,
    device_type text,
    time_of_day text,
    algorithm_version text
);

\copy movies FROM '/csv/movies.csv' WITH (FORMAT csv, HEADER true)
\copy users FROM '/csv/users.csv' WITH (FORMAT csv, HEADER true)
\copy watch_history FROM '/csv/watch_history.csv' WITH (FORMAT csv, HEADER true)
\copy search_logs FROM '/csv/search_logs.csv' WITH (FORMAT csv, HEADER true)
\copy reviews FROM '/csv/reviews.csv' WITH (FORMAT csv, HEADER true)
\copy recommendation_logs FROM '/csv/recommendation_logs.csv' WITH (FORMAT csv, HEADER true)

CREATE INDEX idx_movies_movie_id ON movies (movie_id);
CREATE INDEX idx_users_user_id ON users (user_id);
CREATE INDEX idx_watch_history_session_id ON watch_history (session_id);
CREATE INDEX idx_watch_history_user_id ON watch_history (user_id);
CREATE INDEX idx_watch_history_movie_id ON watch_history (movie_id);
CREATE INDEX idx_search_logs_search_id ON search_logs (search_id);
CREATE INDEX idx_search_logs_user_id ON search_logs (user_id);
CREATE INDEX idx_reviews_review_id ON reviews (review_id);
CREATE INDEX idx_reviews_user_id ON reviews (user_id);
CREATE INDEX idx_reviews_movie_id ON reviews (movie_id);
CREATE INDEX idx_recommendation_logs_recommendation_id ON recommendation_logs (recommendation_id);
CREATE INDEX idx_recommendation_logs_user_id ON recommendation_logs (user_id);
CREATE INDEX idx_recommendation_logs_movie_id ON recommendation_logs (movie_id);
