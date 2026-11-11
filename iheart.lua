-- {"name":"iHeartRadio Favorites","file":"","version":0,"order":3,"arguments":[]}
local service = "http://127.0.0.1:18767"
local args = mympd_arguments

local function encode(value)
    return value:gsub("([^%w_.~-])", function(char)
        return string.format("%%%02X", string.byte(char))
    end)
end

local function request(path)
    local rc, status, _, body = mympd.http_client(
        "GET", service .. path, "", "", false
    )
    if rc == 0 and status == 200 then
        return json.decode(body)
    end
end

local function picker(title, stations, field, show_search, allow_add)
    local fields = {}
    if #stations > 0 then
        local ids, names = {}, {}
        for _, station in ipairs(stations) do
            ids[#ids + 1] = station.id
            names[#names + 1] = station.name
        end
        fields[#fields + 1] = {
            name = field, type = "select", value = ids,
            displayValue = names, defaultValue = ids[1]
        }
    end
    if show_search then
        fields[#fields + 1] = {
            name = "Search by station name or call sign",
            type = "text", value = ""
        }
    end
    if show_search and args.mode ~= "play" then
        fields[#fields + 1] = {
            name = "Search podcasts", type = "text", value = ""
        }
    end
    if allow_add then
        fields[#fields + 1] = {
            name = "station_action", type = "select",
            value = {"play", "save"},
            displayValue = {"Play selected station", "Add to iHeartRadio favorites"},
            defaultValue = "play"
        }
    end
    return mympd.dialog(title, fields, "iHeartRadio Favorites")
end

local function play(uri, name)
    local rc, result = mympd.api("MYMPD_API_QUEUE_APPEND_URIS", {
        uris = {uri}, play = true
    })
    if rc ~= 0 then
        return result.message or "Could not start playback"
    end
    return "Started " .. name
end

local podcast_query = args["Search podcasts"]
if type(podcast_query) == "string" and podcast_query:match("%S") then
    if #podcast_query > 100 then
        return "Enter a podcast search of up to 100 characters"
    end
    local shows = request("/podcasts?q=" .. encode(podcast_query))
    if not shows then
        return "Could not search iHeartRadio podcasts"
    end
    if #shows == 0 then
        return "No iHeartRadio podcasts found"
    end
    return picker("Choose a podcast", shows, "podcast")
end

if type(args.podcast) == "string" and args.podcast:match("^%d+$") then
    local episodes = request("/podcasts/" .. args.podcast)
    if not episodes then
        return "Could not load podcast episodes"
    end
    if #episodes == 0 then
        return "No episodes found"
    end
    return picker("Choose a recent episode", episodes, "episode")
end

if type(args.episode) == "string" and args.episode:match("^%d+$") then
    local episode = request("/episodes/" .. args.episode)
    if not episode then
        return "Could not resolve the podcast episode"
    end
    return play(episode.url, episode.name)
end

local query = args["Search by station name or call sign"]
if type(query) == "string" and query:match("%S") then
    if #query > 100 then
        return "Enter a station name or call sign up to 100 characters"
    end
    local results = request("/search?q=" .. encode(query))
    if not results then
        return "Could not search iHeartRadio"
    end
    if #results == 0 then
        return "No iHeartRadio stations found"
    end
    return picker("iHeartRadio search results", results, "station", false, true)
end

if args.station ~= nil then
    if type(args.station) ~= "string" or not args.station:match("^%d+$") then
        return "Select an iHeartRadio station"
    end
    if args.station_action == "save" then
        local rc, status = mympd.http_client(
            "POST", service .. "/favorites/" .. args.station,
            "Content-Type: application/json\r\n", "{}", false
        )
        if rc == 0 and status == 204 then
            return "Station added to iHeartRadio favorites"
        end
        return "Could not add the station to iHeartRadio favorites"
    end
    local stream = request("/stations/" .. args.station)
    if not stream then
        return "Could not resolve the iHeartRadio stream"
    end
    local uri = stream.url:gsub("#.*$", "") .. "#mympd-iheart=" .. args.station
        .. "&name=" .. encode(stream.name) .. "&art=" .. encode(stream.artFile or "")
    return play(uri, stream.name)
end

local stations = request("/stations")
if not stations then
    return "Could not load iHeartRadio favorites"
end
return picker("iHeartRadio Favorites", stations, "station", true)
