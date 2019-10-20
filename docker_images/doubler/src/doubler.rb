$stdout.sync = true

@ROYO_GET input
output = (input*2).to_json
@ROYO_PUT output
