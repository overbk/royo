FROM ruby:2.6

WORKDIR /app

RUN apt-get update && apt-get install -y net-tools && apt-get clean && rm -rf /var/lib/apt/lists

# Install gems
ADD src/Gemfile* /app
RUN bundle install

# Upload source
ADD src /app

CMD ["ruby", "paritychecker.rb"]
