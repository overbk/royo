$stdout.sync = true

@ROYO_GET input
puts "==> reporter received:\n" + JSON.pretty_generate(input)
