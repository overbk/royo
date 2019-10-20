$stdout.sync = true

@ROYO_GET input
output = { number: input, is_even: input % 2 == 0 }.to_json
@ROYO_PUT output
