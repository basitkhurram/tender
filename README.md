Text "right" for food that you find yumm, or text "left" for food that you find dumb.

Tender is an "SMS Based Application" that lets you send text messages to a server to help decide what sort of cuisine
you, or you and a group of companions, may want to eat.

At a high level view, users send text messages to a Twilio number. Twilio communicates users' messages to Tender via a
web hook. Since SMS is a stateless protocol, redis is used as a data store to maintain session history for users. Using
users' session histories, Tender is able to carry out two-way conversations with users.

Tender asks a user for the user's location and then sends the user images of cuisines that are served by nearby businesses. The user indicates a
preference for the cuisines represented by the images sent by Tender. After the user has been presented with some customizable number of
images, the user is presented with a suggestion for a cuisine and an eatery that serves the suggested cuisine.

Tender also offers users the ability to create a party. Once a party has been created by a user, the user can send the
party's identifier to companions and allow them to join the party too. Party members can then collectively vote on
cuisines.

This project was meant as a learning exercise and to primarily allow me to play a little with Twilio. Note, the code in
this repository makes use of different APIs to pull images and location information (Flickr, Getty, Google, Yelp,
and Yummly to name a few). Usage of these APIs requires compliance with their associated terms and agreements. If you
use this repository, ensure that you give the proper attributions.
