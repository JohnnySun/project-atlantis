-- Bounded B3TJ startup harness for an owned mGBA process.
--
-- This writes only active-low KEYINPUT values into r1 immediately after the
-- reviewed KEYINPUT load.  It never writes state bytes, object fields, save
-- data or ROM.  The receipt is metadata-only and belongs in /private/tmp.

local out = assert(io.open("/private/tmp/b3tj-navigation-harness.jsonl", "w"))

local function hx(value)
    return string.format("0x%08X", (value or 0) & 0xFFFFFFFF)
end

local function rd(name)
    return (emu:readRegister(name) or 0) & 0xFFFFFFFF
end

local function state_line()
    return string.format(
        "next=%s current=%s previous=%s",
        hx(emu:read8(0x02000000)),
        hx(emu:read8(0x02000001)),
        hx(emu:read8(0x02000002))
    )
end

local function emit(tag, ...)
    local fields = { ... }
    for index = 1, #fields do
        fields[index] = tostring(fields[index])
    end
    out:write(tag .. " " .. table.concat(fields, " ") .. "\n")
    out:flush()
end

local NO_KEY = 0x03FF
local START = 0x03F7
local A = 0x03FE
local start_gate_seen = false
local start_sent = false
local a1ac_seen = false
local a_sent = false
local releases = 0
local state7_seen = false
local max_frames = 6000

emit(
    "META",
    "game=B3TJ",
    "mode=bounded-startup-state7",
    "input_semantics=active-low-r1-after-load",
    "writes_state=false",
    "writes_object=false",
    "writes_save=false",
    "writes_rom=false"
)

local function install_breakpoint(address, name, callback)
    local id = emu:setBreakpoint(callback, address)
    emit("BP_INSTALL", "name=" .. name, "addr=" .. hx(address), "id=" .. tostring(id))
end

local function install()
    install_breakpoint(0x0800A050, "state4_input_gate", function()
        if not start_gate_seen then
            start_gate_seen = true
            emit("STATE4_GATE", "frame=" .. tostring(emu:currentFrame()), state_line(), "pc=" .. hx(rd("pc")), "lr=" .. hx(rd("lr")))
        end
    end)

    install_breakpoint(0x0800A1AC, "a1ac", function()
        a1ac_seen = true
        emit("A1AC", "frame=" .. tostring(emu:currentFrame()), state_line(), "r0=" .. hx(rd("r0")), "lr=" .. hx(rd("lr")))
    end)

    install_breakpoint(0x080A85D8, "state7", function()
        state7_seen = true
        emit("STATE7", "frame=" .. tostring(emu:currentFrame()), state_line(), "pc=" .. hx(rd("pc")), "lr=" .. hx(rd("lr")))
    end)

    install_breakpoint(0x08000E14, "keyinput_postread", function()
        local value = NO_KEY
        local phase = "release"
        local emit_event = false
        if start_gate_seen and not start_sent then
            value = START
            start_sent = true
            phase = "start"
            emit_event = true
        elseif a1ac_seen and not a_sent then
            value = A
            a_sent = true
            phase = "a"
            emit_event = true
        elseif a1ac_seen and releases < 8 then
            releases = releases + 1
            emit_event = true
        end
        emu:writeRegister("r1", value)
        if emit_event then
            emit(
                "KEYINPUT",
                "frame=" .. tostring(emu:currentFrame()),
                "phase=" .. phase,
                "active_low=" .. hx(value),
                state_line(),
                "r1=" .. hx(rd("r1"))
            )
        end
    end)
end

local installed = false

callbacks:add("keysRead", function()
    emu:setKeys(0x0000)
end)

callbacks:add("frame", function()
    if not installed and emu:currentFrame() >= 1 then
        installed = true
        install()
    end
    if emu:currentFrame() >= max_frames then
        emit(
            "END",
            "frame=" .. tostring(emu:currentFrame()),
            "state7_seen=" .. tostring(state7_seen),
            "start_sent=" .. tostring(start_sent),
            "a_sent=" .. tostring(a_sent),
            "releases=" .. tostring(releases),
            state_line()
        )
        out:close()
        os.exit(0)
    end
end)
