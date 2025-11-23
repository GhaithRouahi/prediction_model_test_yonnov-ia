import csv

input_file = 'Predict/Test_Data/listings.csv'
output_file = 'Predict/Test_Data/listings_cleaned.csv'

with open(input_file, 'r', newline='', encoding='utf-8') as infile, \
     open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    reader = csv.reader(infile)
    writer = csv.writer(outfile)

    header = next(reader)
    writer.writerow(header)

    for row in reader:
        # Check if all fields are non-empty
        if all(field.strip() for field in row):
            writer.writerow(row)

print(f"Cleaned data saved to {output_file}")